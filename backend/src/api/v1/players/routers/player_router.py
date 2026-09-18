from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.v1.auth.services.dependencies import JwtDataDep
from src.api.v1.players.dtos.player_dtos import PlayerResponse
from src.infra.postgres.interfaces.player_repository_interface import PlayerRepositoryInterface
from src.infra.postgres.repositories.player_repository import get_player_repository

router = APIRouter(prefix="/players", tags=["players"])

PlayerRepositoryDep = Annotated[PlayerRepositoryInterface, Depends(get_player_repository)]


@router.get("", response_model=list[PlayerResponse], summary="List players")
async def list_players(
    repository: PlayerRepositoryDep,
    _: JwtDataDep,
    limit: int = 100,
    offset: int = 0,
) -> list[PlayerResponse]:
    players = await repository.list(limit=limit, offset=offset)
    return [PlayerResponse.from_domain(player) for player in players]


@router.get(
    "/{player_id}",
    response_model=PlayerResponse,
    summary="Get a player by id",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Player not found"}},
)
async def get_player(
    player_id: int, repository: PlayerRepositoryDep, _: JwtDataDep
) -> PlayerResponse:
    player = await repository.get(player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return PlayerResponse.from_domain(player)
