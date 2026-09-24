"""Admin-only lookup of `real_player` rows -- backs the "correct match"
picker on the identity-link review page: given a doubtful match, the admin
searches for the real Transfermarkt player it should actually link to.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

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


@router.get(
    "/search",
    response_model=list[RealPlayerSummary],
    summary="Search real_player by name for the identity-link correct-match picker",
)
async def search_real_players(
    q: str,
    repository: RealPlayerRepositoryDep,
    admin: AdminDep,
    limit: int = 20,
    offset: int = 0,
) -> list[RealPlayerSummary]:
    results = await repository.search(q, limit=limit, offset=offset)
    return [RealPlayerSummary.from_domain(player) for player in results]
