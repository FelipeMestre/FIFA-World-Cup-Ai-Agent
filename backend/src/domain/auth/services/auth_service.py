from src.domain.auth.exceptions.auth_exceptions import InvalidCredentials
from src.domain.auth.model.user import User
from src.domain.auth.services import password_service, token_service
from src.infra.postgres.interfaces.user_repository_interface import UserRepositoryInterface


class AuthService:
    """Orchestrates the login use case: look up the user, verify the password,
    and issue a JWT. Kept in the domain layer (not the router) because it
    coordinates a repository lookup with the token/password domain services.
    """

    def __init__(self, user_repository: UserRepositoryInterface) -> None:
        self._user_repository = user_repository

    async def login(self, email: str, password: str) -> tuple[User, str]:
        user = await self._user_repository.get_by_email(email)
        if user is None or not password_service.verify_password(password, user.password_hash):
            raise InvalidCredentials()
        token = token_service.create_access_token(user)
        return user, token
