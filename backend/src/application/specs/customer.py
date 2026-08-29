"""The reads the customer use cases need, one class each.

Written against ``CustomerModel``, not ``Customer`` (ADR 0007). Customers
are not name-unique (people share names, PRD §4.2), so there is no
uniqueness probe here. ``CustomerBrowse`` carries its filters as plain
attributes so the in-memory fake can read them without an ORM.
"""

from uuid import UUID

from sqlalchemy import or_

from application.common.specification import Specification
from infrastructure.persistence.tenant.models import CustomerModel


class CustomerForWrite(Specification[CustomerModel]):
    """Locks the row for a command that loads a customer to mutate it."""

    def __init__(self, customer_id: UUID) -> None:
        super().__init__(CustomerModel)
        self.customer_id = customer_id
        self.where(CustomerModel.id == customer_id)
        self.lock()


class CustomerBrowse(Specification[CustomerModel]):
    """The customer list: case-insensitive match over name and phone,
    optional active filter, oldest first."""

    def __init__(self, search: str | None = None, is_active: bool | None = None) -> None:
        super().__init__(CustomerModel)
        self.search = search
        self.is_active = is_active
        if search:
            term = f"%{search.strip()}%"
            self.where(
                or_(
                    CustomerModel.full_name.ilike(term),
                    CustomerModel.phone.ilike(term),
                )
            )
        if is_active is not None:
            self.where(CustomerModel.is_active.is_(is_active))
        self.order(CustomerModel.created_at, CustomerModel.id)
