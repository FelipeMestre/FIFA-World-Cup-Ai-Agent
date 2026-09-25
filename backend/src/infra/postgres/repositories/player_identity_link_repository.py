"""Point-read/update repository for `player_identity_link`, plus a bulk
`upsert_candidates` composed on top of the generic `IngestionRepositoryInterface`
(reuses its `ON CONFLICT DO UPDATE` SQL instead of duplicating it).
"""

from decimal import Decimal
from typing import Annotated

from fastapi import Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestion.exceptions.ingestion_exceptions import (
    IdentityLinkNotFoundError,
    RealPlayerAlreadyLinkedError,
    RealPlayerNotFoundError,
)
from src.domain.ingestion.model.player_identity_candidate import PlayerIdentityCandidate
from src.domain.ingestion.model.player_identity_link import (
    LinkReviewStatus,
    PlayerIdentityLink,
    PlayerMatchMethod,
)
from src.domain.ingestion.model.player_identity_link_review import PlayerIdentityLinkReview
from src.domain.ingestion.model.real_player import RealPlayer
from src.domain.players.model.player import Player
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.ingestion_repository_interface import UpsertResult
from src.infra.postgres.interfaces.player_identity_link_repository_interface import (
    PlayerIdentityLinkRepositoryInterface,
)
from src.infra.postgres.repositories.ingestion_repository import _SqlAlchemyIngestionRepository
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema
from src.infra.postgres.schemas.player_identity_link_schema import (
    LinkReviewStatus as SchemaLinkReviewStatus,
)
from src.infra.postgres.schemas.player_identity_link_schema import (
    PlayerIdentityLinkSchema,
)
from src.infra.postgres.schemas.player_identity_link_schema import (
    PlayerMatchMethod as SchemaPlayerMatchMethod,
)
from src.infra.postgres.schemas.player_schema import PlayerSchema
from src.infra.postgres.schemas.real_player_schema import RealPlayerSchema

# Auto-accept threshold shared with the spec's confidence-tiered matching
# requirement: candidates at or above this confidence are persisted as
# already-approved, system-reviewed links (`reviewed_by_user_id=None`
# distinguishes this from an admin approval); below it they are queued as
# `pending` for `GET /admin/identity-links/pending` review.
_AUTO_ACCEPT_CONFIDENCE = Decimal("0.950")


def _dedupe_by_real_player_id(
    candidates: list[PlayerIdentityCandidate],
) -> list[PlayerIdentityCandidate]:
    """`real_player_id` is unique in `player_identity_link`: a real
    Transfermarkt player can back at most one synthetic roster player. The
    matching pipeline scores each synthetic player independently, so two
    different synthetic players can both pick the same real player as their
    best candidate -- a same-batch collision `ON CONFLICT (player_id)`
    cannot resolve, since the conflict target doesn't cover
    `real_player_id`. Keep only the highest-confidence candidate per real
    player; the loser is left unmatched for this sync rather than wrongly
    linked (found live: a real sync run hit this exact constraint violation).
    """
    best_by_real_player_id: dict[int, PlayerIdentityCandidate] = {}
    for candidate in candidates:
        current_best = best_by_real_player_id.get(candidate.real_player_id)
        if current_best is None or (candidate.match_confidence or Decimal("-1")) > (
            current_best.match_confidence or Decimal("-1")
        ):
            best_by_real_player_id[candidate.real_player_id] = candidate
    return list(best_by_real_player_id.values())


def _to_domain(row: PlayerIdentityLinkSchema) -> PlayerIdentityLink:
    return PlayerIdentityLink(
        id=row.id,
        player_id=row.player_id,
        real_player_id=row.real_player_id,
        match_method=PlayerMatchMethod(row.match_method.value),
        match_confidence=row.match_confidence,
        status=LinkReviewStatus(row.status.value),
        reviewed_by_user_id=row.reviewed_by_user_id,
        created_at=row.created_at,
    )


def _synthetic_player_to_domain(row: PlayerSchema) -> Player:
    return Player(
        id=row.player_id,
        team_id=row.team_id,
        name=row.player_name,
        position=row.position,
        club_team=row.club_team,
        market_value_eur=row.market_value_eur,
        caps=row.caps,
        date_of_birth=row.date_of_birth,
        height_cm=row.height_cm,
        goals=row.goals,
    )


def _real_player_to_domain(row: RealPlayerSchema) -> RealPlayer:
    return RealPlayer(
        player_id=row.player_id,
        first_name=row.first_name,
        last_name=row.last_name,
        date_of_birth=row.date_of_birth,
        country_of_birth=row.country_of_birth,
        country_of_citizenship=row.country_of_citizenship,
        position=row.position,
        sub_position=row.sub_position,
        foot=row.foot,
        height_cm=row.height_cm,
        current_club_id=row.current_club_id,
        current_national_team_id=row.current_national_team_id,
        international_caps=row.international_caps,
        international_goals=row.international_goals,
        market_value_eur=row.market_value_eur,
        highest_market_value_eur=row.highest_market_value_eur,
        contract_expiration_date=row.contract_expiration_date,
        profile_url=row.profile_url,
        last_synced_at=row.last_synced_at,
    )


class _SqlAlchemyPlayerIdentityLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._ingestion_repository = _SqlAlchemyIngestionRepository(session)

    async def list_by_status(
        self, status: LinkReviewStatus | None, limit: int = 100, offset: int = 0
    ) -> list[PlayerIdentityLinkReview]:
        # Joins in both sides of the proposed match (the synthetic roster
        # player and the Transfermarkt real_player), plus the roster
        # player's national_team for its country name (Player.team_id
        # alone isn't a nationality an admin can read), so the admin review
        # list carries every comparison field in one call -- no per-row
        # follow-up lookup for any side. `status=None` is the admin's "all
        # statuses" filter option, not just the default "pending" view.
        query = (
            select(
                PlayerIdentityLinkSchema,
                PlayerSchema,
                RealPlayerSchema,
                NationalTeamSchema.team_name,
            )
            .join(PlayerSchema, PlayerSchema.player_id == PlayerIdentityLinkSchema.player_id)
            .join(
                RealPlayerSchema,
                RealPlayerSchema.player_id == PlayerIdentityLinkSchema.real_player_id,
            )
            .join(NationalTeamSchema, NationalTeamSchema.team_id == PlayerSchema.team_id)
        )
        if status is not None:
            query = query.where(
                PlayerIdentityLinkSchema.status == SchemaLinkReviewStatus(status.value)
            )
        result = await self._session.execute(
            query.order_by(PlayerIdentityLinkSchema.id).limit(limit).offset(offset)
        )
        return [
            PlayerIdentityLinkReview(
                link=_to_domain(link_row),
                synthetic_player=_synthetic_player_to_domain(player_row),
                synthetic_player_nationality=team_name,
                real_player=_real_player_to_domain(real_player_row),
            )
            for link_row, player_row, real_player_row, team_name in result.all()
        ]

    async def count_by_status(self, status: LinkReviewStatus | None) -> int:
        query = select(func.count(PlayerIdentityLinkSchema.id))
        if status is not None:
            query = query.where(
                PlayerIdentityLinkSchema.status == SchemaLinkReviewStatus(status.value)
            )
        result = await self._session.execute(query)
        return result.scalar_one()

    async def get(self, link_id: int) -> PlayerIdentityLink | None:
        row = await self._session.get(PlayerIdentityLinkSchema, link_id)
        return _to_domain(row) if row else None

    async def update_status(
        self, link_id: int, status: LinkReviewStatus, reviewed_by_user_id: int | None
    ) -> PlayerIdentityLink:
        row = await self._session.get(PlayerIdentityLinkSchema, link_id)
        if row is None:
            raise IdentityLinkNotFoundError(f"player_identity_link {link_id} not found")
        row.status = SchemaLinkReviewStatus(status.value)
        row.reviewed_by_user_id = reviewed_by_user_id
        row.reviewed_by_admin = reviewed_by_user_id is not None
        await self._session.commit()
        await self._session.refresh(row)
        return _to_domain(row)

    async def reassign(
        self, link_id: int, new_real_player_id: int, admin_user_id: int
    ) -> PlayerIdentityLink:
        row = await self._session.get(PlayerIdentityLinkSchema, link_id)
        if row is None:
            raise IdentityLinkNotFoundError(f"player_identity_link {link_id} not found")

        real_player_row = await self._session.get(RealPlayerSchema, new_real_player_id)
        if real_player_row is None:
            raise RealPlayerNotFoundError(f"real_player {new_real_player_id} not found")

        # real_player_id is unique on player_identity_link -- validated
        # up front (rather than letting the UPDATE hit the constraint) so
        # the failure is a clear domain exception, not a raw IntegrityError.
        conflict = await self._session.execute(
            select(PlayerIdentityLinkSchema.id).where(
                PlayerIdentityLinkSchema.real_player_id == new_real_player_id,
                PlayerIdentityLinkSchema.id != link_id,
            )
        )
        if conflict.scalar_one_or_none() is not None:
            raise RealPlayerAlreadyLinkedError(
                f"real_player {new_real_player_id} is already linked to a different "
                "player_identity_link"
            )

        row.real_player_id = new_real_player_id
        row.match_method = SchemaPlayerMatchMethod.MANUAL
        row.match_confidence = None
        row.status = SchemaLinkReviewStatus.APPROVED
        row.reviewed_by_user_id = admin_user_id
        row.reviewed_by_admin = True
        await self._session.commit()
        await self._session.refresh(row)
        return _to_domain(row)

    async def upsert_candidates(self, candidates: list[PlayerIdentityCandidate]) -> UpsertResult:
        if not candidates:
            return UpsertResult(table_name="player_identity_link", row_count=0)
        candidates = _dedupe_by_real_player_id(candidates)
        rows = [
            {
                "player_id": candidate.player_id,
                "real_player_id": candidate.real_player_id,
                "match_method": SchemaPlayerMatchMethod(candidate.match_method.value),
                "match_confidence": candidate.match_confidence,
                "status": (
                    SchemaLinkReviewStatus.APPROVED
                    if candidate.match_confidence >= _AUTO_ACCEPT_CONFIDENCE
                    else SchemaLinkReviewStatus.PENDING
                ),
                "reviewed_by_user_id": None,
            }
            for candidate in candidates
        ]
        return await self._ingestion_repository.upsert_many(
            PlayerIdentityLinkSchema, rows, conflict_columns=("player_id",)
        )

    async def delete_all(self) -> int:
        result = await self._session.execute(delete(PlayerIdentityLinkSchema))
        await self._session.commit()
        return result.rowcount


def get_player_identity_link_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PlayerIdentityLinkRepositoryInterface:
    return _SqlAlchemyPlayerIdentityLinkRepository(session)
