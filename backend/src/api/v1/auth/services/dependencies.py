"""Reusable auth dependencies other bounded contexts import to require a
logged-in user (`parse_jwt_data`) or an admin (`require_admin`) -- these are
application services per AGENTS.md: reusable pieces of logic, not use-case
orchestration.
"""

from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.domain.auth.services.token_service import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=True)


async def parse_jwt_data(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> dict[str, Any]:
    try:
        return decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


JwtDataDep = Annotated[dict[str, Any], Depends(parse_jwt_data)]


async def require_admin(token_data: JwtDataDep) -> dict[str, Any]:
    if not token_data.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return token_data
