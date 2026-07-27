import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import ActivatableRow, TenantBase


class LocationModel(TenantBase, ActivatableRow):
    """A store, a stockroom, a warehouse (PRD §4.2).

    Names are unique within the store: provisioning already seeds one, and
    two rows called "Warehouse" would make the location column on every
    movement ambiguous to whoever reads the report.
    """

    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
