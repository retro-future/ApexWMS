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

    ``__abstract__ = True`` is what makes this an *abstract declarative
    base* rather than a plain mixin: SQLAlchemy still copies these columns
    into each concrete subclass's own table exactly as a mixin would (no
    shared table, no shared ``Column`` objects), but — unlike a plain
    mixin, which must not inherit ``DeclarativeBase`` — this class genuinely
    *is* one. That is what lets ``TenantCrudRepository`` bind its ``ModelT``
    to ``TenantActivatableRow`` while still satisfying ``CrudRepository``'s
    own ``ModelT: DeclarativeBase`` bound, which in turn is what lets
    ``SqlRepository._insert`` be typed as ``DeclarativeBase`` instead of
    ``object``.

    Declared once here rather than per model so ``TenantCrudRepository``
    can *require* these columns: it is the upper bound on the repository's
    model parameter, which is what lets ``_browse_page`` filter and order
    without each subclass re-supplying its own columns.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
