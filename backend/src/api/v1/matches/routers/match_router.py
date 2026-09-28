from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.v1.auth.services.dependencies import JwtDataDep
from src.api.v1.matches.dtos.match_dtos import MatchResponse, MatchSearchResultDto
from src.infra.postgres.interfaces.match_repository_interface import MatchRepositoryInterface
from src.infra.postgres.repositories.match_repository import get_match_repository

router = APIRouter(prefix="/matches", tags=["matches"])

MatchRepositoryDep = Annotated[MatchRepositoryInterface, Depends(get_match_repository)]


@router.get("", response_model=list[MatchResponse], summary="List matches")
async def list_matches(
    repository: MatchRepositoryDep,
    _: JwtDataDep,
    limit: int = 100,
    offset: int = 0,
) -> list[MatchResponse]:
    matches = await repository.list(limit=limit, offset=offset)
    return [MatchResponse.from_domain(match) for match in matches]


@router.get(
    "/search",
    response_model=list[MatchSearchResultDto],
    summary="Search matches by team name for the match-selector chip",
    description="Matches either team's name/FIFA code against `q` "
    "(case/diacritic-insensitive substring). An empty `q` returns every "
    "match, so the chip can list all of them before the user types anything. "
    "Not paginated -- the whole tournament is ~100 matches, so even an "
    "unfiltered result set is always small.",
)
async def search_matches(
    repository: MatchRepositoryDep,
    _: JwtDataDep,
    q: Annotated[str, Query()] = "",
) -> list[MatchSearchResultDto]:
    rows = await repository.search(q)
    return [MatchSearchResultDto.from_domain(row) for row in rows]


@router.get(
    "/{match_id}",
    response_model=MatchResponse,
    summary="Get a match by id",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Match not found"}},
)
async def get_match(match_id: int, repository: MatchRepositoryDep, _: JwtDataDep) -> MatchResponse:
    match = await repository.get(match_id)
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    return MatchResponse.from_domain(match)
