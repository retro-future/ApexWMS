"""A third-party financing partner (PRD §4.2, §4.7).

Uzum Nasiya, Alif Nasiya and the like. A label on a financed sale and
nothing more: the company pays the store in full at sale time, so there is
no receivable, no payout schedule, no commission and no rate to track. If
one ever starts paying late or short, the sales are already labelled by
company, so the history survives the redesign that would follow.
"""

from dataclasses import dataclass
from datetime import datetime

from domain.core import TenantEntity, UuidEntity


@dataclass(eq=False, kw_only=True)
class CreditCompany(UuidEntity, TenantEntity):
    name: str
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool
    created_at: datetime
