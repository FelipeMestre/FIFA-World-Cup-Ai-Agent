"""Managed Postgres providers (Render, Heroku, ...) hand out `postgres://` or
`postgresql://` URLs, but the async engine needs the `+asyncpg` driver marker.
`PostgresConfig` normalizes the scheme so the env var can be wired verbatim.
"""

import pytest

from src.infra.postgres.config import PostgresConfig

ASYNC_URL = "postgresql+asyncpg://user:pw@host:5432/db"


@pytest.mark.parametrize(
    "raw_url",
    [
        "postgresql://user:pw@host:5432/db",
        "postgres://user:pw@host:5432/db",
        ASYNC_URL,
    ],
)
def test_database_url_is_normalized_to_asyncpg_scheme(raw_url: str):
    assert PostgresConfig(DATABASE_URL=raw_url).DATABASE_URL == ASYNC_URL


def test_database_url_with_other_driver_is_left_untouched():
    url = "postgresql+psycopg://user:pw@host:5432/db"
    settings = PostgresConfig(DATABASE_URL=url)
    assert url == settings.DATABASE_URL
