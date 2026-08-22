"""Domain services: business rules that belong to no single entity.

``PriceResolver`` needs a unit *and* its product, ``UnitProjector`` needs a
whole movement history, and ``SubtotalsCalculator`` needs a document's whole
line set — none has a natural home on one class. All are stateless: every
method is a pure function of its arguments, with no I/O whatsoever (PRD
§7.3), which is what makes the rules they carry testable with a couple of
objects and no database.
"""

from domain.services.pricing import PriceResolver
from domain.services.projection import UnitProjector
from domain.services.subtotals import SubtotalsCalculator

__all__ = [
    "PriceResolver",
    "SubtotalsCalculator",
    "UnitProjector",
]
