"""Who the store sells to (PRD §4.2).

Deliberately anemic: name and phone. This is not a CRM. What a customer
*owes* is not stored here either — it is derived from their invoices and
payments (§4.7), so there is no balance field to drift.
"""

from dataclasses import dataclass
from datetime import datetime

from domain.core import TenantEntity, UuidEntity


@dataclass(eq=False, kw_only=True)
class Customer(UuidEntity, TenantEntity):
    full_name: str
    phone: str | None = None
    is_active: bool
    created_at: datetime
