"""A tenant: one store business, one physical database (PRD §3)."""

from dataclasses import dataclass
from datetime import datetime

from domain.core import MasterEntity, UuidEntity
from domain.tenancy import TenantStatus


@dataclass(eq=False, kw_only=True)
class Tenant(UuidEntity, MasterEntity):
    name: str
    status: TenantStatus
    created_at: datetime
