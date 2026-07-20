"""A global user account (MasterDB). Tenant roles live on Membership."""

from dataclasses import dataclass
from datetime import datetime

from domain.core import MasterEntity, UuidEntity


@dataclass(eq=False, kw_only=True)
class User(UuidEntity, MasterEntity):
    email: str
    full_name: str
    # None until an invited user sets their password (FR-1.5).
    password_hash: str | None
    is_active: bool
    created_at: datetime
