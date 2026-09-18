from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.auth.model.user import User
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.user_repository_interface import UserRepositoryInterface
from src.infra.postgres.schemas.auth_schema import UserSchema


def _to_domain(row: UserSchema) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        is_admin=row.is_admin,
        created_at=row.created_at,
    )


class _SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserSchema).where(UserSchema.email == email))
        row = result.scalar_one_or_none()
        return _to_domain(row) if row else None


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRepositoryInterface:
    return _SqlAlchemyUserRepository(session)
