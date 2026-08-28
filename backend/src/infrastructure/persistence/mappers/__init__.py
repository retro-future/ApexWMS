"""One mapper per aggregate root. A child entity is mapped by a private
method of its root's mapper, never by a mapper of its own.

Mappers are not split by database: a mapper holds no session, so nothing
about it is master- or tenant-specific. The two sides differ in which
*session* a repository gets, not in how a row becomes an entity.

``COMMON_MAPPERS`` is what the container builds its ``MapperRegistry``
from — converting an aggregate means writing its mapper and adding one name
here. The instances are built at import: a mapper is stateless, so one of
each is all there will ever be.
"""

from infrastructure.persistence.mappers.purchase_order import PurchaseOrderMapper
from infrastructure.persistence.mappers.registry import (
    MapperRegistry,
    UnmappedModelError,
)
from infrastructure.persistence.mappers.supplier import SupplierMapper
from infrastructure.persistence.mappers.supplier_return import SupplierReturnMapper

COMMON_MAPPERS = (SupplierMapper(), PurchaseOrderMapper(), SupplierReturnMapper())

__all__ = [
    "COMMON_MAPPERS",
    "MapperRegistry",
    "PurchaseOrderMapper",
    "SupplierMapper",
    "SupplierReturnMapper",
    "UnmappedModelError",
]
