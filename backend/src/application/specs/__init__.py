"""Specifications — one class per read a use case performs, grouped by
aggregate. See ADR 0007 for why these are written against ORM models."""

from application.specs.purchase_order import (
    PurchaseOrderBrowse,
    PurchaseOrderById,
    PurchaseOrderForWrite,
)
from application.specs.supplier import (
    SupplierBrowse,
    SupplierById,
    SupplierByName,
    SupplierForWrite,
    SupplierNameTakenByAnother,
)
from application.specs.supplier_return import (
    SupplierReturnBrowse,
    SupplierReturnById,
    SupplierReturnForWrite,
)

__all__ = [
    "PurchaseOrderBrowse",
    "PurchaseOrderById",
    "PurchaseOrderForWrite",
    "SupplierBrowse",
    "SupplierById",
    "SupplierByName",
    "SupplierForWrite",
    "SupplierNameTakenByAnother",
    "SupplierReturnBrowse",
    "SupplierReturnById",
    "SupplierReturnForWrite",
]
