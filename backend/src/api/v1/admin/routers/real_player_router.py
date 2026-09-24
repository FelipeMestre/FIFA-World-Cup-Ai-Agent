"""Admin-only lookup of `real_player` rows -- backs the "correct match"
picker on the identity-link review page: given a doubtful match, the admin
searches for the real Transfermarkt player it should actually link to.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.api.v1.admin.dtos.identity_link_dtos import RealPlayerSummary
from src.api.v1.auth.services.dependencies import require_admin
from src.infra.postgres.interfaces.real_player_repository_interface import (
    RealPlayerRepositoryInterface,
)
from src.infra.postgres.repositories.real_player_repository import get_real_player_repository

router = APIRouter(prefix="/admin/real-players", tags=["admin-real-players"])

AdminDep = Annotated[dict, Depends(require_admin)]
RealPlayerRepositoryDep = Annotated[
    RealPlayerRepositoryInterface, Depends(get_real_player_repository)
]

# `real_player` can hold every Transfermarkt player (tens of thousands of
# rows) -- these bounds are enforced by FastAPI at the request boundary
# (a 422, not a silent clamp) so a caller can never force the repository's
# already-paginated query into fetching an unbounded result set.
_MAX_SEARCH_LIMIT = 50


@router.get(
    "/search",
    response_model=list[RealPlayerSummary],
    summary="Search real_player by name for the identity-link correct-match picker",
)
async def search_real_players(
    repository: RealPlayerRepositoryDep,
    admin: AdminDep,
    q: Annotated[str, Query(min_length=2, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=_MAX_SEARCH_LIMIT)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RealPlayerSummary]:
    results = await repository.search(q, limit=limit, offset=offset)
    return [RealPlayerSummary.from_domain(player) for player in results]
