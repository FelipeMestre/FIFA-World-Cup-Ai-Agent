from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.v1.auth.dtos.auth_dtos import CurrentUserResponse, LoginRequest, LoginResponse
from src.api.v1.auth.services.dependencies import JwtDataDep
from src.domain.auth.config import auth_settings
from src.domain.auth.exceptions.auth_exceptions import InvalidCredentials
from src.domain.auth.services.auth_service import AuthService
from src.infra.postgres.interfaces.user_repository_interface import UserRepositoryInterface
from src.infra.postgres.repositories.user_repository import get_user_repository

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(
    user_repository: Annotated[UserRepositoryInterface, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(user_repository)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with email and password",
    description="Verifies credentials against the stored bcrypt hash and issues a JWT token.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid email or password"},
    },
)
async def login(payload: LoginRequest, auth_service: AuthServiceDep) -> LoginResponse:
    try:
        _, token = await auth_service.login(payload.email, payload.password)
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc
    return LoginResponse(access_token=token, expires_in_minutes=auth_settings.EXP_MINUTES)


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Return the authenticated user",
    description=(
        "Loads the user identified by the JWT `sub` claim. "
        "Used by the app shell to show the display name."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing, invalid, or expired token"},
    },
)
async def get_me(
    token_data: JwtDataDep,
    user_repository: Annotated[UserRepositoryInterface, Depends(get_user_repository)],
) -> CurrentUserResponse:
    try:
        user_id = int(token_data["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    user = await user_repository.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_admin=user.is_admin,
    )
