from datetime import datetime

from sqlalchemy import Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class TenantBase(DeclarativeBase):
    pass


class ActivatableRow:
    """The two columns every tenant-side record carries.

    ``is_active`` because nothing in this system hard-deletes (FR-2.4) —
    a record leaves circulation by being deactivated, so its history keeps
    resolving. ``created_at`` because "oldest first" is the default order
    every list endpoint pages by.

    Declared once here rather than per model so ``TenantCrudRepository``
    can *require* them: it is the upper bound on the repository's model
    parameter, which is what lets ``_browse_page`` filter and order
    without each subclass re-supplying its own columns.
    """

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
