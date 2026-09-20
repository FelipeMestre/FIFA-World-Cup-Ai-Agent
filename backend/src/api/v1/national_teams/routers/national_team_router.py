from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.v1.auth.services.dependencies import JwtDataDep
from src.api.v1.national_teams.dtos.national_team_dtos import NationalTeamResponse
from src.infra.postgres.interfaces.national_team_repository_interface import (
    NationalTeamRepositoryInterface,
)
from src.infra.postgres.repositories.national_team_repository import get_national_team_repository

router = APIRouter(prefix="/national-teams", tags=["national-teams"])

NationalTeamRepositoryDep = Annotated[
    NationalTeamRepositoryInterface, Depends(get_national_team_repository)
]


@router.get("", response_model=list[NationalTeamResponse], summary="List national teams")
async def list_national_teams(
    repository: NationalTeamRepositoryDep,
    _: JwtDataDep,
    limit: int = 100,
    offset: int = 0,
) -> list[NationalTeamResponse]:
    national_teams = await repository.list(limit=limit, offset=offset)
    return [NationalTeamResponse.from_domain(team) for team in national_teams]


@router.get(
    "/{team_id}",
    response_model=NationalTeamResponse,
    summary="Get a national team by id",
    responses={status.HTTP_404_NOT_FOUND: {"description": "National team not found"}},
)
async def get_national_team(
    team_id: int, repository: NationalTeamRepositoryDep, _: JwtDataDep
) -> NationalTeamResponse:
    national_team = await repository.get(team_id)
    if national_team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="National team not found")
    return NationalTeamResponse.from_domain(national_team)
