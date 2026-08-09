"""Domain services: business rules that belong to no single entity.

``PriceResolver`` needs a unit *and* its product, and ``UnitProjector``
needs a whole movement history — neither has a natural home on one class.
Both are stateless: every method is a pure function of its arguments, with
no I/O whatsoever (PRD §7.3), which is what makes the rules they carry
testable with a couple of objects and no database.
"""

from domain.services.pricing import PriceResolver
from domain.services.projection import UnitProjector

__all__ = [
    "PriceResolver",
    "UnitProjector",
]
