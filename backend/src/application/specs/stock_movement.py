"""Whole-row reads of the stock ledger (§4.3). Written against
``StockMovementModel`` (ADR 0007).

The projection reads (the FR-9.5 log, ``units_sold``, ``net_quantity``, the
on-hand and moved-pair sweeps) return read-model rows or scalars, not
movements, so they live in ``StockMovementQueries`` (`query-services.md`).
Each spec here stores its filters as plain attributes for the in-memory
fake.
"""

from uuid import UUID

from application.common.specification import Specification
from domain.enums import DocumentType
from infrastructure.persistence.tenant.models import StockMovementModel


class MovementsForDocument(Specification[StockMovementModel]):
    """Everything one document wrote — what a cancellation compensates."""

    def __init__(self, document_type: DocumentType, document_id: UUID) -> None:
        super().__init__(StockMovementModel)
        self.document_type = document_type
        self.document_id = document_id
        self.where(
            StockMovementModel.document_type == document_type.value,
            StockMovementModel.document_id == document_id,
        )
        self.order(StockMovementModel.occurred_at, StockMovementModel.id)


class MovementsForUnit(Specification[StockMovementModel]):
    """One handset's whole life, oldest first — the IMEI trace (FR-9.2)."""

    def __init__(self, device_unit_id: UUID) -> None:
        super().__init__(StockMovementModel)
        self.device_unit_id = device_unit_id
        self.where(StockMovementModel.device_unit_id == device_unit_id)
        self.order(StockMovementModel.occurred_at, StockMovementModel.id)


class MovementsForPair(Specification[StockMovementModel]):
    """One quantity product's movements at one location, in order — the
    sequence a cost pool is replayed from (§4.6)."""

    def __init__(self, product_id: UUID, location_id: UUID) -> None:
        super().__init__(StockMovementModel)
        self.product_id = product_id
        self.location_id = location_id
        self.where(
            StockMovementModel.product_id == product_id,
            StockMovementModel.location_id == location_id,
            StockMovementModel.device_unit_id.is_(None),
        )
        self.order(StockMovementModel.occurred_at, StockMovementModel.id)
