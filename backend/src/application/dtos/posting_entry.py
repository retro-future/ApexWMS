"""One thing a document did, as goods **and** as money (PRD §4.3, §4.6).

The two ledgers are written in the same database transaction or neither is
(FR-10.1), and this is the shape that makes that structural rather than
conventional: a caller cannot describe a stock effect without saying what
it did to the money, because the two arrive in one object.

``money`` is a list rather than a single amount because one stock effect
routinely has two financial consequences: selling a handset books
``SALE_REVENUE`` and ``COGS`` against the same movement. It may also be
empty — confirming a Purchase Order moves nothing at all (§4.4), and a
stock count that finds a unit exactly where it should be adjusts nothing.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from domain.enums import DeviceStatus, DocumentType, MovementType, TransactionType
from domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class MoneyEffect:
    """One financial consequence of a stock effect.

    ``amount`` is signed, in the product's own currency, and nothing here
    converts (§4.5 rule 1).
    """

    txn_type: TransactionType
    amount: Money
    note: str | None = None


@dataclass(frozen=True, slots=True)
class PostingEntry:
    """A stock effect and the money it moved.

    ``device_unit_id`` is set for a serialized line and ``None`` for a
    quantity one — the two tracking types write to the same ledger (§4.1),
    and this is what tells them apart. ``new_status``/``new_location_id``
    are the projection this movement implies for that unit; they are
    stated by the caller rather than inferred, because only the document
    knows whether a ``-1`` means sold, written off, or returned.
    """

    movement_type: MovementType
    product_id: UUID
    location_id: UUID
    quantity_delta: int
    device_unit_id: UUID | None = None
    new_status: DeviceStatus | None = None
    new_location_id: UUID | None = None
    money: Sequence[MoneyEffect] = field(default_factory=tuple)
    note: str | None = None


@dataclass(frozen=True, slots=True)
class Posting:
    """Everything one confirmed document did, in one atomic act.

    Naming the document once rather than on every entry is not tidiness:
    it is what guarantees the whole posting shares one cause, which is what
    makes "reverse document X" a query rather than a reconstruction.
    """

    document_type: DocumentType
    document_id: UUID
    entries: Sequence[PostingEntry]
