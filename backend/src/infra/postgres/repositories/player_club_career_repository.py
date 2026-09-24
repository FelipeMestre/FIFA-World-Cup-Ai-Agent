"""Approved-link read of Transfermarkt profile and transfers.

The join runs when the player-analysis tool runs. `player_stat` is not
touched, so club numbers cannot move a World Cup percentile.
"""

from decimal import Decimal
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.player_analytics.model.player_analysis import (
    ApprovedClubCareer,
    PlayerClubProfile,
    PlayerTransfer,
)
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.player_club_career_repository_interface import (
    PlayerClubCareerRepositoryInterface,
)
from src.infra.postgres.schemas.player_identity_link_schema import (
    LinkReviewStatus as SchemaLinkReviewStatus,
)
from src.infra.postgres.schemas.player_identity_link_schema import PlayerIdentityLinkSchema
from src.infra.postgres.schemas.real_organization_schema import RealClubSchema
from src.infra.postgres.schemas.real_player_schema import RealPlayerSchema, RealTransferSchema


def _whole_euros(amount: Decimal | int | None) -> int | None:
    if amount is None:
        return None
    return int(Decimal(amount).to_integral_value())


class _SqlAlchemyPlayerClubCareerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_approved_career(self, player_id: int) -> ApprovedClubCareer | None:
        linked = await self._load_approved_player(player_id)
        if linked is None:
            return None
        real_player, club_name = linked
        transfers = await self._load_transfers(real_player.player_id)
        return ApprovedClubCareer(
            profile=PlayerClubProfile(
                preferred_foot=real_player.foot,
                sub_position=real_player.sub_position,
                height_cm=real_player.height_cm,
                date_of_birth=real_player.date_of_birth,
                citizenship=real_player.country_of_citizenship,
                current_club=club_name,
                market_value_eur=real_player.market_value_eur,
                highest_market_value_eur=real_player.highest_market_value_eur,
                international_caps=real_player.international_caps,
                international_goals=real_player.international_goals,
            ),
            transfers=tuple(transfers),
        )

    async def _load_approved_player(
        self, player_id: int
    ) -> tuple[RealPlayerSchema, str | None] | None:
        stmt = (
            select(RealPlayerSchema, RealClubSchema.name)
            .join(
                PlayerIdentityLinkSchema,
                PlayerIdentityLinkSchema.real_player_id == RealPlayerSchema.player_id,
            )
            .outerjoin(RealClubSchema, RealClubSchema.club_id == RealPlayerSchema.current_club_id)
            .where(
                PlayerIdentityLinkSchema.player_id == player_id,
                PlayerIdentityLinkSchema.status == SchemaLinkReviewStatus.APPROVED,
            )
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    async def _load_transfers(self, real_player_id: int) -> list[PlayerTransfer]:
        stmt = (
            select(RealTransferSchema)
            .where(RealTransferSchema.real_player_id == real_player_id)
            .order_by(RealTransferSchema.transfer_date, RealTransferSchema.id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            PlayerTransfer(
                transfer_date=row.transfer_date,
                season=row.transfer_season,
                from_club=row.from_club_name,
                to_club=row.to_club_name,
                fee_eur=_whole_euros(row.transfer_fee_eur),
                market_value_eur=_whole_euros(row.market_value_at_transfer_eur),
            )
            for row in rows
        ]


def build_player_club_career_repository(
    session: AsyncSession,
) -> PlayerClubCareerRepositoryInterface:
    return _SqlAlchemyPlayerClubCareerRepository(session)


def get_player_club_career_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PlayerClubCareerRepositoryInterface:
    return build_player_club_career_repository(session)
