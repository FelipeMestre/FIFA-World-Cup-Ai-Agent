from datetime import UTC, date, datetime

import pytest

from src.domain.ingestion.exceptions.ingestion_exceptions import (
    IdentityLinkAlreadyReviewedError,
    IdentityLinkNotFoundError,
)
from src.domain.ingestion.model.player_identity_link import (
    LinkReviewStatus,
    PlayerIdentityLink,
    PlayerMatchMethod,
)
from src.domain.ingestion.model.player_identity_link_review import PlayerIdentityLinkReview
from src.domain.ingestion.model.real_player import RealPlayer
from src.domain.ingestion.services.identity_link_review_service import (
    PlayerIdentityLinkReviewService,
)
from src.domain.players.model.player import Player


def _link(link_id: int, status: LinkReviewStatus) -> PlayerIdentityLink:
    return PlayerIdentityLink(
        id=link_id,
        player_id=1,
        real_player_id=100,
        match_method=PlayerMatchMethod.FUZZY_NAME,
        match_confidence=None,
        status=status,
        reviewed_by_user_id=None,
        created_at=datetime.now(UTC),
    )


def _synthetic_player() -> Player:
    return Player(1, 1, "Test Player", "FWD", "Test FC", 1000000, 5, date(2000, 1, 1), 180, 3)


def _real_player() -> RealPlayer:
    return RealPlayer(
        player_id=100,
        first_name="Test",
        last_name="Player",
        date_of_birth=date(2000, 1, 1),
        country_of_birth=None,
        country_of_citizenship=None,
        position="Forward",
        sub_position=None,
        foot=None,
        height_cm=180,
        current_club_id=None,
        current_national_team_id=None,
        international_caps=None,
        international_goals=None,
        market_value_eur=None,
        highest_market_value_eur=None,
        contract_expiration_date=None,
        profile_url="https://example.test",
        last_synced_at=datetime.now(UTC),
    )


def _review(link_id: int, status: LinkReviewStatus) -> PlayerIdentityLinkReview:
    return PlayerIdentityLinkReview(
        link=_link(link_id, status),
        synthetic_player=_synthetic_player(),
        synthetic_player_nationality="Testland",
        real_player=_real_player(),
    )


class _FakeRepository:
    def __init__(self, links: dict[int, PlayerIdentityLink]) -> None:
        self._links = links
        self.update_calls: list[tuple[int, LinkReviewStatus, int | None]] = []
        self.reassign_calls: list[tuple[int, int, int]] = []

    async def list_pending(
        self, limit: int = 100, offset: int = 0
    ) -> list[PlayerIdentityLinkReview]:
        pending = [
            _review(link.id, link.status)
            for link in self._links.values()
            if link.status == LinkReviewStatus.PENDING
        ]
        return pending[offset : offset + limit]

    async def get(self, link_id: int) -> PlayerIdentityLink | None:
        return self._links.get(link_id)

    async def update_status(
        self, link_id: int, status: LinkReviewStatus, reviewed_by_user_id: int | None
    ) -> PlayerIdentityLink:
        self.update_calls.append((link_id, status, reviewed_by_user_id))
        updated = _link(link_id, status)
        self._links[link_id] = updated
        return updated

    async def reassign(
        self, link_id: int, new_real_player_id: int, admin_user_id: int
    ) -> PlayerIdentityLink:
        self.reassign_calls.append((link_id, new_real_player_id, admin_user_id))
        updated = PlayerIdentityLink(
            id=link_id,
            player_id=self._links[link_id].player_id,
            real_player_id=new_real_player_id,
            match_method=PlayerMatchMethod.MANUAL,
            match_confidence=None,
            status=LinkReviewStatus.APPROVED,
            reviewed_by_user_id=admin_user_id,
            created_at=self._links[link_id].created_at,
        )
        self._links[link_id] = updated
        return updated

    async def upsert_candidates(self, candidates):  # pragma: no cover - unused here
        raise NotImplementedError


@pytest.mark.asyncio
async def test_list_pending_returns_only_pending_links():
    repository = _FakeRepository(
        {1: _link(1, LinkReviewStatus.PENDING), 2: _link(2, LinkReviewStatus.APPROVED)}
    )
    service = PlayerIdentityLinkReviewService(repository)

    result = await service.list_pending()

    assert [review.link.id for review in result] == [1]


@pytest.mark.asyncio
async def test_approve_sets_status_and_reviewer():
    repository = _FakeRepository({1: _link(1, LinkReviewStatus.PENDING)})
    service = PlayerIdentityLinkReviewService(repository)

    result = await service.approve(link_id=1, admin_user_id=42)

    assert result.status == LinkReviewStatus.APPROVED
    assert repository.update_calls == [(1, LinkReviewStatus.APPROVED, 42)]


@pytest.mark.asyncio
async def test_reject_sets_status_and_reviewer():
    repository = _FakeRepository({1: _link(1, LinkReviewStatus.PENDING)})
    service = PlayerIdentityLinkReviewService(repository)

    result = await service.reject(link_id=1, admin_user_id=42)

    assert result.status == LinkReviewStatus.REJECTED
    assert repository.update_calls == [(1, LinkReviewStatus.REJECTED, 42)]


@pytest.mark.asyncio
async def test_approve_unknown_link_raises_not_found():
    repository = _FakeRepository({})
    service = PlayerIdentityLinkReviewService(repository)

    with pytest.raises(IdentityLinkNotFoundError):
        await service.approve(link_id=999, admin_user_id=42)


@pytest.mark.asyncio
async def test_approve_already_reviewed_link_raises():
    repository = _FakeRepository({1: _link(1, LinkReviewStatus.APPROVED)})
    service = PlayerIdentityLinkReviewService(repository)

    with pytest.raises(IdentityLinkAlreadyReviewedError):
        await service.approve(link_id=1, admin_user_id=42)


@pytest.mark.asyncio
async def test_reassign_delegates_to_repository_without_requiring_pending():
    # Unlike approve/reject, reassign works on an already-reviewed link too --
    # it's how the admin corrects a match the pipeline auto-approved wrong.
    repository = _FakeRepository({1: _link(1, LinkReviewStatus.APPROVED)})
    service = PlayerIdentityLinkReviewService(repository)

    result = await service.reassign(link_id=1, new_real_player_id=200, admin_user_id=42)

    assert result.real_player_id == 200
    assert result.match_method == PlayerMatchMethod.MANUAL
    assert result.status == LinkReviewStatus.APPROVED
    assert repository.reassign_calls == [(1, 200, 42)]
