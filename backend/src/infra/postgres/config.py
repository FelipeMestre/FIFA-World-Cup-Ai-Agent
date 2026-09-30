from collections.abc import AsyncGenerator

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_ASYNCPG_SCHEME = "postgresql+asyncpg://"
_PLAIN_POSTGRES_SCHEMES = ("postgresql://", "postgres://")


class PostgresConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str

    @field_validator("DATABASE_URL")
    @classmethod
    def _use_asyncpg_driver(cls, url: str) -> str:
        """Managed Postgres providers hand out `postgres://` / `postgresql://`
        URLs; the async engine (and Alembic's async env) needs `+asyncpg`."""
        for plain_scheme in _PLAIN_POSTGRES_SCHEMES:
            if url.startswith(plain_scheme):
                return _ASYNCPG_SCHEME + url[len(plain_scheme) :]
        return url


postgres_settings = PostgresConfig()

engine = create_async_engine(postgres_settings.DATABASE_URL, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
