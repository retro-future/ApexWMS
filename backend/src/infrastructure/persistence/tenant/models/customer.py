from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import ActivatableRow, TenantBase


class CustomerModel(TenantBase, ActivatableRow):
    """Who this store sells to (PRD §4.2).

    ``full_name`` is indexed but *not* unique: two people share a name, and
    refusing the second at the till would be absurd. ``phone`` is indexed
    because that is what a seller actually has to search by.

    No balance column: what a customer owes is derived from their invoices
    and payments (§4.7), so there is nothing here to drift from the ledger.
    """

    __tablename__ = "customers"

    full_name: Mapped[str] = mapped_column(String(200), index=True)
    phone: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
