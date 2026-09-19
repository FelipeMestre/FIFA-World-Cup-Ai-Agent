"""Point-read/update repository for `player_identity_link`, plus a bulk
`upsert_candidates` composed on top of the generic `IngestionRepositoryInterface`
(reuses its `ON CONFLICT DO UPDATE` SQL instead of duplicating it).
"""

from decimal import Decimal
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestion.exceptions.ingestion_exceptions import IdentityLinkNotFoundError
from src.domain.ingestion.model.player_identity_candidate import PlayerIdentityCandidate
from src.domain.ingestion.model.player_identity_link import (
    LinkReviewStatus,
    PlayerIdentityLink,
    PlayerMatchMethod,
)
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.ingestion_repository_interface import UpsertResult
from src.infra.postgres.interfaces.player_identity_link_repository_interface import (
    PlayerIdentityLinkRepositoryInterface,
)
from src.infra.postgres.repositories.ingestion_repository import _SqlAlchemyIngestionRepository
from src.infra.postgres.schemas.player_identity_link_schema import (
    LinkReviewStatus as SchemaLinkReviewStatus,
)
from src.infra.postgres.schemas.player_identity_link_schema import (
    PlayerIdentityLinkSchema,
)
from src.infra.postgres.schemas.player_identity_link_schema import (
    PlayerMatchMethod as SchemaPlayerMatchMethod,
)

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


class _SqlAlchemyPlayerIdentityLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._ingestion_repository = _SqlAlchemyIngestionRepository(session)

    async def list_pending(self, limit: int = 100, offset: int = 0) -> list[PlayerIdentityLink]:
        result = await self._session.execute(
            select(PlayerIdentityLinkSchema)
            .where(PlayerIdentityLinkSchema.status == SchemaLinkReviewStatus.PENDING)
            .order_by(PlayerIdentityLinkSchema.id)
            .limit(limit)
            .offset(offset)
        )
        return [_to_domain(row) for row in result.scalars().all()]

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


def get_player_identity_link_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PlayerIdentityLinkRepositoryInterface:
    return _SqlAlchemyPlayerIdentityLinkRepository(session)
