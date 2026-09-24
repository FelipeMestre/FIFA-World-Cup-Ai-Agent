from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class UserSchema(Base):
    __tablename__ = "user"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(name)) BETWEEN 1 AND 128",
            name="name_not_blank",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    is_admin: Mapped[bool] = mapped_column(nullable=False, default=False)
    # timezone=True -> TIMESTAMPTZ: the app always creates tz-aware UTC datetimes.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
