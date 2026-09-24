from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class User:
    id: int
    email: str
    name: str
    password_hash: str
    is_admin: bool
    created_at: datetime
