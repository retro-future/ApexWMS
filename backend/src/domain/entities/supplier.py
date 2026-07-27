"""Who the store buys from (PRD §4.2).

No currency field: currency belongs to the product (§4.5 rule 3), not to
the supplier or to the document. The same supplier may sell phones priced
in dollars and cases priced in som on one purchase order.
"""

from dataclasses import dataclass
from datetime import datetime

from domain.core import TenantEntity, UuidEntity


@dataclass(eq=False, kw_only=True)
class Supplier(UuidEntity, TenantEntity):
    name: str
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool
    created_at: datetime
