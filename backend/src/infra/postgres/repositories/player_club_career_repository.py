"""Approved-link read of Transfermarkt profile and transfers.

The join runs when the player-analysis tool runs. `player_stat` is not
touched, so club numbers cannot move a World Cup percentile.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.player_analytics.competition_names import competition_name
from src.domain.player_analytics.model.player_analysis import (
    ApprovedClubCareer,
    PlayerClubProfile,
    PlayerSeasonStat,
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
from src.infra.postgres.schemas.real_player_schema import (
    RealPlayerSchema,
    RealPlayerSeasonStatSchema,
    RealTransferSchema,
)


def _whole_euros(amount: Decimal | int | None) -> int | None:
    if amount is None:
        return None
    return int(Decimal(amount).to_integral_value())


def _season_start_year(season: str) -> int | None:
    head = season.split("/", 1)[0].strip()
    if not head.isdigit():
        return None
    year = int(head)
    if year < 100:
        return 2000 + year
    return year


def _is_retired(career_seasons: list[PlayerSeasonStat], latest_known_year: int) -> bool:
    """No season-stat row within the dataset's last two known seasons.

    A player with no season rows at all trivially qualifies (`default=0`).
    Relative to the dataset's own latest known season, not wall-clock time --
    this is a synthetic/snapshot dataset, not live data.
    """
    latest_played_year = max(
        (_season_start_year(season.season) or 0 for season in career_seasons), default=0
    )
    return latest_played_year < latest_known_year - 1


def club_at_season_midpoint(season: str, transfers: list[PlayerTransfer]) -> str | None:
    """Club registered on 1 January after the season's start year.

    Transfermarkt seasons are labeled by the year they begin (July). January
    is the middle of that season, so a summer move lands on the new club and
    a move the following summer does not.
    """
    start_year = _season_start_year(season)
    if start_year is None:
        return None
    midpoint = date(start_year + 1, 1, 1)
    club: str | None = None
    for transfer in transfers:
        if transfer.transfer_date > midpoint:
            break
        club = transfer.to_club
    return club


class _SqlAlchemyPlayerClubCareerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_approved_career(self, player_id: int) -> ApprovedClubCareer | None:
        linked = await self._load_approved_player(player_id)
        if linked is None:
            return None
        real_player, club_name = linked
        return await self._build_career(real_player, club_name)

    async def get_career_by_real_player_id(self, real_player_id: int) -> ApprovedClubCareer:
        real_player, club_name = await self._load_real_player(real_player_id)
        return await self._build_career(real_player, club_name)

    async def _build_career(
        self, real_player: RealPlayerSchema, club_name: str | None
    ) -> ApprovedClubCareer:
        transfers = await self._load_transfers(real_player.player_id)
        career_seasons = await self._load_career_seasons(real_player.player_id, transfers)
        latest_known_year = await self._load_latest_known_season_year()
        is_retired = _is_retired(career_seasons, latest_known_year)
        return ApprovedClubCareer(
            profile=PlayerClubProfile(
                preferred_foot=real_player.foot,
                sub_position=real_player.sub_position,
                height_cm=real_player.height_cm,
                date_of_birth=real_player.date_of_birth,
                citizenship=real_player.country_of_citizenship,
                current_club=None if is_retired else club_name,
                market_value_eur=real_player.market_value_eur,
                highest_market_value_eur=real_player.highest_market_value_eur,
                international_caps=real_player.international_caps,
                international_goals=real_player.international_goals,
                is_retired=is_retired,
            ),
            transfers=tuple(transfers),
            career_seasons=tuple(career_seasons),
        )

    async def _load_latest_known_season_year(self) -> int:
        stmt = select(func.max(RealPlayerSeasonStatSchema.season))
        latest_season = (await self._session.execute(stmt)).scalar_one_or_none()
        if latest_season is None:
            return 0
        return _season_start_year(latest_season) or 0

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

    async def _load_real_player(self, real_player_id: int) -> tuple[RealPlayerSchema, str | None]:
        stmt = (
            select(RealPlayerSchema, RealClubSchema.name)
            .outerjoin(RealClubSchema, RealClubSchema.club_id == RealPlayerSchema.current_club_id)
            .where(RealPlayerSchema.player_id == real_player_id)
        )
        row = (await self._session.execute(stmt)).one()
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

    async def _load_career_seasons(
        self, real_player_id: int, transfers: list[PlayerTransfer]
    ) -> list[PlayerSeasonStat]:
        stat = RealPlayerSeasonStatSchema
        stmt = select(
            stat.season,
            stat.competition_id,
            stat.appearances,
            stat.minutes_played,
            stat.goals,
            stat.assists,
            stat.yellow_cards,
            stat.red_cards,
        ).where(stat.real_player_id == real_player_id)
        rows = (await self._session.execute(stmt)).all()
        seasons = [
            PlayerSeasonStat(
                season=season,
                team=club_at_season_midpoint(season, transfers),
                competition_id=competition_id,
                competition=competition_name(competition_id),
                appearances=int(appearances),
                minutes=int(minutes),
                goals=int(goals),
                assists=int(assists),
                yellow_cards=int(yellow_cards),
                red_cards=int(red_cards),
            )
            for (
                season,
                competition_id,
                appearances,
                minutes,
                goals,
                assists,
                yellow_cards,
                red_cards,
            ) in rows
        ]
        seasons.sort(
            key=lambda row: (
                -(_season_start_year(row.season) or 0),
                row.season,
                -row.appearances,
                row.competition,
            )
        )
        return seasons


def build_player_club_career_repository(
    session: AsyncSession,
) -> PlayerClubCareerRepositoryInterface:
    return _SqlAlchemyPlayerClubCareerRepository(session)


def get_player_club_career_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PlayerClubCareerRepositoryInterface:
    return build_player_club_career_repository(session)
