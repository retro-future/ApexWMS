"""Reads for the ``(product, location) -> quantity`` projection (§4.2).

Written against ``StockLevelModel`` (ADR 0007). Only the pair lookup is a
class — every posting service does it. The one-off location snapshot and
"every level" reads are inline in their handlers.
"""

from uuid import UUID

from application.common.specification import Specification
from infrastructure.persistence.tenant.models import StockLevelModel


class StockLevelForPair(Specification[StockLevelModel]):
    """The one level for a ``(product, location)`` pair, or none."""

    def __init__(self, product_id: UUID, location_id: UUID) -> None:
        super().__init__(StockLevelModel)
        self.product_id = product_id
        self.location_id = location_id
        self.where(
            StockLevelModel.product_id == product_id,
            StockLevelModel.location_id == location_id,
        )
