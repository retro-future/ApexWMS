"""The reads the write-off use cases need, one class each.

Written against ``WriteOffModel``, not ``WriteOff`` (ADR 0007). Every spec
eager-loads ``lines`` and, per line, the ``product`` (currency and
tracking type) and the nullable ``device_unit`` (the scanned IMEI). Same
shape as ``supplier_return.py``.
"""

from uuid import UUID

from sqlalchemy.orm import selectinload

from application.common.specification import Specification
from domain.enums import DocumentStatus, WriteOffReason
from infrastructure.persistence.tenant.models import WriteOffLineModel, WriteOffModel

_WITH_LINES = (
    selectinload(WriteOffModel.lines).selectinload(WriteOffLineModel.product),
    selectinload(WriteOffModel.lines).selectinload(WriteOffLineModel.device_unit),
)


class WriteOffById(Specification[WriteOffModel]):
    """Read-only: no lock. For the reads that only display a write-off."""

    def __init__(self, write_off_id: UUID) -> None:
        super().__init__(WriteOffModel)
        self.write_off_id = write_off_id
        self.where(WriteOffModel.id == write_off_id)
        self.include(*_WITH_LINES)


class WriteOffForWrite(Specification[WriteOffModel]):
    """The specification a command uses to load a write-off it will mutate.

    Scanning, unscanning, confirming and cancelling all load through this:
    it locks ``write_offs`` and brings the whole line collection so the
    mapper can sync it.
    """

    def __init__(self, write_off_id: UUID) -> None:
        super().__init__(WriteOffModel)
        self.write_off_id = write_off_id
        self.where(WriteOffModel.id == write_off_id)
        self.include(*_WITH_LINES)
        self.lock()


class WriteOffBrowse(Specification[WriteOffModel]):
    """The write-off list: number substring match, optional status,
    location and reason filters, newest first with ``id`` as the
    tie-break."""

    def __init__(
        self,
        search: str | None = None,
        status: DocumentStatus | None = None,
        location_id: UUID | None = None,
        reason: WriteOffReason | None = None,
    ) -> None:
        super().__init__(WriteOffModel)
        self.search = search
        self.status = status
        self.location_id = location_id
        self.reason = reason
        if search:
            self.where(WriteOffModel.number.ilike(f"%{search.strip()}%"))
        if status is not None:
            self.where(WriteOffModel.status == status.value)
        if location_id is not None:
            self.where(WriteOffModel.location_id == location_id)
        if reason is not None:
            self.where(WriteOffModel.reason == reason.value)
        self.include(*_WITH_LINES)
        self.order(WriteOffModel.created_at.desc(), WriteOffModel.id)
