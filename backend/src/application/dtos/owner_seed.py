"""The Owner's ``Employee`` row that provisioning writes into a new store."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class OwnerSeed:
    """The Owner's ``Employee`` row that provisioning writes into a new store.

    ``user_id`` is the master ``User.id`` and becomes ``Employee.id`` — the
    equality the ledger's foreign keys depend on from M3.
    """

    user_id: UUID
    email: str
    full_name: str
