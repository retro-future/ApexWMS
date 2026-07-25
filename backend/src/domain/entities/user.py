"""The login identity: one row per person, in MasterDB (PRD §3.1).

This is "who is this person", and it is deliberately separate from "what
can they do at store X" — that is the ``Employee`` row in the store's own
database. A person who works at two stores has **one** User and two
Employees.

``tenant_id`` is the person's home store, stamped into their access token
at login. It is null for platform operators (SuperAdmin/Admin), who
belong to no store and get no tenant claim at all.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.core import MasterEntity, UuidEntity


@dataclass(eq=False, kw_only=True)
class User(UuidEntity, MasterEntity):
    email: str
    full_name: str
    # None until an invited user sets their password (FR-1.5).
    password_hash: str | None
    # None for an app-level user; otherwise the store they log into by default.
    tenant_id: UUID | None = None
    is_active: bool
    # True for an Owner seeded at provisioning with a temporary password.
    must_change_password: bool = False
    created_at: datetime
