"""The reads the supplier use cases need, one class each.

Written against ``SupplierModel``, not ``Supplier`` — ADR 0007.
"""

from uuid import UUID

from sqlalchemy import or_

from application.common.specification import Specification
from infrastructure.persistence.tenant.models import SupplierModel


class SupplierForWrite(Specification[SupplierModel]):
    """The specification a command uses to load a supplier it will mutate.

    Locks the row, so two concurrent renames cannot both read the old name,
    both pass the uniqueness probe, and both write. Suppliers hold no
    collections, so there is nothing to eager-load alongside it.
    """

    def __init__(self, supplier_id: UUID) -> None:
        super().__init__(SupplierModel)
        self.supplier_id = supplier_id
        self.where(SupplierModel.id == supplier_id)
        self.lock()


class SupplierBrowse(Specification[SupplierModel]):
    """The supplier list: case-insensitive substring match over name,
    contact and phone, optional active filter, oldest first.

    The tie-break on ``id`` is what makes the order total: rows created
    inside the same clock tick would otherwise sort arbitrarily, and two
    arbitrary sorts of the same table can show one row on both pages and
    another on neither.
    """

    def __init__(self, search: str | None = None, is_active: bool | None = None) -> None:
        super().__init__(SupplierModel)
        if search:
            term = f"%{search.strip()}%"
            self.where(
                or_(
                    SupplierModel.name.ilike(term),
                    SupplierModel.contact_name.ilike(term),
                    SupplierModel.phone.ilike(term),
                )
            )
        if is_active is not None:
            self.where(SupplierModel.is_active.is_(is_active))
        self.order(SupplierModel.created_at, SupplierModel.id)
