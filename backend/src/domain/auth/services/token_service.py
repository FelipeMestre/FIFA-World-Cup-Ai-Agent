from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from src.domain.auth.config import auth_settings
from src.domain.auth.model.user import User


def create_access_token(user: User) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "is_admin": user.is_admin,
        "iat": now,
        "exp": now + timedelta(minutes=auth_settings.EXP_MINUTES),
    }
    return jwt.encode(payload, auth_settings.SECRET, algorithm=auth_settings.ALG)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, auth_settings.SECRET, algorithms=[auth_settings.ALG])
