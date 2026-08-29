import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class TenantBase(DeclarativeBase):
    pass


class TenantActivatableRow(TenantBase):
    """The three columns every browsable tenant-side record carries.

    ``is_active`` because nothing in this system hard-deletes (FR-2.4) —
    a record leaves circulation by being deactivated, so its history keeps
    resolving. ``created_at`` because "oldest first" is the default order
    every list endpoint pages by, and ``id`` because that order needs a
    unique tie-break to page stably.

    ``__abstract__ = True`` makes this an abstract declarative base rather
    than a plain mixin: SQLAlchemy copies these columns into each concrete
    subclass's own table (no shared table, no shared ``Column`` objects),
    but the class genuinely is a ``DeclarativeBase``. The browse
    specifications (``application/specs/*.py``) read ``created_at``/``id``
    for their total ordering and ``is_active`` for the active filter.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
