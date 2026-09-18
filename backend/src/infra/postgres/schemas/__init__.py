"""Import every schema module so `Base.metadata` is fully populated before
Alembic autogenerate (or any `Base.metadata.create_all`) inspects it.
"""

from src.infra.postgres.schemas import (  # noqa: F401
    auth_schema,
    match_schema,
    player_identity_link_schema,
    player_schema,
    real_organization_schema,
    real_player_schema,
    reference_schema,
    team_schema,
)
from src.infra.postgres.schemas.base import Base

__all__ = ["Base"]
