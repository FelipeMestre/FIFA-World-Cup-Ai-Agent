"""Non-DI equivalent of `infra/postgres/config.py`'s `get_db` for use inside
Arq task functions, which run outside FastAPI's request-scoped `Depends`
graph and so cannot use `Depends(get_db)` directly.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.postgres.config import SessionFactory


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
