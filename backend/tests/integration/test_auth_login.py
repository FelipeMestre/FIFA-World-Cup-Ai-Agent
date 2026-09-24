"""Integration tests for POST /api/v1/auth/login.

Per AGENTS.md's testing guidance, this overrides the `UserRepositoryInterface`
dependency (via `app.dependency_overrides`) rather than mocking internals. A
real Postgres-backed integration test is a follow-up once a dedicated test
database is wired into CI -- this fake repository only stands in for the one
`get_by_email` call the login use case makes.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from src.domain.auth.model.user import User
from src.domain.auth.services import password_service
from src.infra.postgres.repositories.user_repository import get_user_repository
from src.main import app

_PASSWORD = "correct horse battery staple"
_EMAIL = "scout@football.ai"


class _FakeUserRepository:
    def __init__(self, user: User) -> None:
        self._user = user

    async def get_by_email(self, email: str) -> User | None:
        return self._user if email == self._user.email else None


@pytest.fixture(autouse=True)
def _override_user_repository() -> AsyncGenerator[None]:
    user = User(
        id=1,
        email=_EMAIL,
        name="Scout",
        password_hash=password_service.hash_password(_PASSWORD),
        is_admin=False,
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_user_repository] = lambda: _FakeUserRepository(user)
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_with_valid_credentials_returns_access_token(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": _EMAIL, "password": _PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


@pytest.mark.asyncio
async def test_login_with_invalid_password_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": _EMAIL, "password": "wrong-password"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_with_unknown_email_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@football.ai", "password": _PASSWORD},
    )

    assert response.status_code == 401
