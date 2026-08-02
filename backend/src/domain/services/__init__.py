"""Domain services: business rules that belong to no single entity.

``resolve_sale_price`` needs a unit *and* its product, and ``CostPool`` is
about a set of goods rather than any one of them — neither has a natural
home on one class, and both are pure functions of their inputs with no I/O
whatsoever (PRD §7.3). They are testable with two objects and no database,
which is exactly the property that makes the rules they carry worth
stating here rather than inside a handler.
"""

from domain.services.pricing import resolve_sale_price, resolve_sale_price_or_none
from domain.services.projection import net_quantity, project_unit_state
from domain.services.valuation import CostPool

__all__ = [
    "CostPool",
    "net_quantity",
    "project_unit_state",
    "resolve_sale_price",
    "resolve_sale_price_or_none",
]
