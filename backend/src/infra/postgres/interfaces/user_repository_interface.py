from typing import Protocol

from src.domain.auth.model.user import User


class UserRepositoryInterface(Protocol):
    async def get_by_email(self, email: str) -> User | None: ...
