from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from src.domain.ingestion.model.player_identity_link import PlayerIdentityLink
from src.domain.ingestion.model.player_identity_link_review import PlayerIdentityLinkReview
from src.domain.ingestion.model.real_player import RealPlayer
from src.domain.players.model.player import Player


class IdentityLinkResponse(BaseModel):
    id: int
    player_id: int
    real_player_id: int
    match_method: str
    match_confidence: Decimal | None
    status: str
    created_at: datetime | None

    @classmethod
    def from_domain(cls, link: PlayerIdentityLink) -> "IdentityLinkResponse":
        return cls(
            id=link.id,
            player_id=link.player_id,
            real_player_id=link.real_player_id,
            match_method=link.match_method.value,
            match_confidence=link.match_confidence,
            status=link.status.value,
            created_at=link.created_at,
        )


class SyntheticPlayerSummary(BaseModel):
    """The WC2026 roster side of a proposed identity-link match."""

    id: int
    team_id: int
    name: str
    position: str
    club_team: str
    market_value_eur: int
    caps: int
    date_of_birth: date
    height_cm: int
    goals: int

    @classmethod
    def from_domain(cls, player: Player) -> "SyntheticPlayerSummary":
        return cls(
            id=player.id,
            team_id=player.team_id,
            name=player.name,
            position=player.position,
            club_team=player.club_team,
            market_value_eur=player.market_value_eur,
            caps=player.caps,
            date_of_birth=player.date_of_birth,
            height_cm=player.height_cm,
            goals=player.goals,
        )


class RealPlayerSummary(BaseModel):
    """The Transfermarkt side of a proposed identity-link match, also
    returned as-is by the real-player search endpoint the "correct match"
    picker uses.
    """

    player_id: int
    first_name: str
    last_name: str
    date_of_birth: date | None
    country_of_birth: str | None
    country_of_citizenship: str | None
    position: str
    sub_position: str | None
    foot: str | None
    height_cm: int | None
    current_club_id: int | None
    current_national_team_id: int | None
    international_caps: int | None
    international_goals: int | None
    market_value_eur: int | None
    highest_market_value_eur: int | None
    profile_url: str

    @classmethod
    def from_domain(cls, real_player: RealPlayer) -> "RealPlayerSummary":
        return cls(
            player_id=real_player.player_id,
            first_name=real_player.first_name,
            last_name=real_player.last_name,
            date_of_birth=real_player.date_of_birth,
            country_of_birth=real_player.country_of_birth,
            country_of_citizenship=real_player.country_of_citizenship,
            position=real_player.position,
            sub_position=real_player.sub_position,
            foot=real_player.foot,
            height_cm=real_player.height_cm,
            current_club_id=real_player.current_club_id,
            current_national_team_id=real_player.current_national_team_id,
            international_caps=real_player.international_caps,
            international_goals=real_player.international_goals,
            market_value_eur=real_player.market_value_eur,
            highest_market_value_eur=real_player.highest_market_value_eur,
            profile_url=real_player.profile_url,
        )


class IdentityLinkReviewResponse(BaseModel):
    """A pending identity-link match plus every comparison field for both
    sides -- the admin review list's response shape, so approving,
    rejecting, or correcting a match needs no follow-up lookup.
    """

    id: int
    match_method: str
    match_confidence: Decimal | None
    status: str
    created_at: datetime | None
    synthetic_player: SyntheticPlayerSummary
    real_player: RealPlayerSummary

    @classmethod
    def from_domain(cls, review: PlayerIdentityLinkReview) -> "IdentityLinkReviewResponse":
        return cls(
            id=review.link.id,
            match_method=review.link.match_method.value,
            match_confidence=review.link.match_confidence,
            status=review.link.status.value,
            created_at=review.link.created_at,
            synthetic_player=SyntheticPlayerSummary.from_domain(review.synthetic_player),
            real_player=RealPlayerSummary.from_domain(review.real_player),
        )
