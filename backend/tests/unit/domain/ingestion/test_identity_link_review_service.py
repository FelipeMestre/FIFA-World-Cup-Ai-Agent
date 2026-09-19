from datetime import UTC, datetime

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
from src.domain.ingestion.services.identity_link_review_service import (
    PlayerIdentityLinkReviewService,
)


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


class _FakeRepository:
    def __init__(self, links: dict[int, PlayerIdentityLink]) -> None:
        self._links = links
        self.update_calls: list[tuple[int, LinkReviewStatus, int | None]] = []

    async def list_pending(self, limit: int = 100, offset: int = 0) -> list[PlayerIdentityLink]:
        pending = [link for link in self._links.values() if link.status == LinkReviewStatus.PENDING]
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

    async def upsert_candidates(self, candidates):  # pragma: no cover - unused here
        raise NotImplementedError


@pytest.mark.asyncio
async def test_list_pending_returns_only_pending_links():
    repository = _FakeRepository(
        {1: _link(1, LinkReviewStatus.PENDING), 2: _link(2, LinkReviewStatus.APPROVED)}
    )
    service = PlayerIdentityLinkReviewService(repository)

    result = await service.list_pending()

    assert [link.id for link in result] == [1]


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
