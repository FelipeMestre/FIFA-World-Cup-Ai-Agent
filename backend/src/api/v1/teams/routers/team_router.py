from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.v1.auth.services.dependencies import JwtDataDep
from src.api.v1.teams.dtos.team_dtos import TeamResponse
from src.infra.postgres.interfaces.team_repository_interface import TeamRepositoryInterface
from src.infra.postgres.repositories.team_repository import get_team_repository

router = APIRouter(prefix="/teams", tags=["teams"])

TeamRepositoryDep = Annotated[TeamRepositoryInterface, Depends(get_team_repository)]


@router.get("", response_model=list[TeamResponse], summary="List teams")
async def list_teams(
    repository: TeamRepositoryDep,
    _: JwtDataDep,
    limit: int = 100,
    offset: int = 0,
) -> list[TeamResponse]:
    teams = await repository.list(limit=limit, offset=offset)
    return [TeamResponse.from_domain(team) for team in teams]


@router.get(
    "/{team_id}",
    response_model=TeamResponse,
    summary="Get a team by id",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Team not found"}},
)
async def get_team(team_id: int, repository: TeamRepositoryDep, _: JwtDataDep) -> TeamResponse:
    team = await repository.get(team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return TeamResponse.from_domain(team)
