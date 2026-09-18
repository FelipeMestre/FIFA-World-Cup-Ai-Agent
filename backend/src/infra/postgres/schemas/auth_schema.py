from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class UserSchema(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    is_admin: Mapped[bool] = mapped_column(nullable=False, default=False)
    # timezone=True -> TIMESTAMPTZ: the app always creates tz-aware UTC datetimes.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
