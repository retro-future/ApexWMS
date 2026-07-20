"""Entity base classes — identity is the id, not the attribute values.

Two handsets of the same model are not equal, even with identical
attributes, because identity is not attributes (PRD §7.6). A plain
dataclass gives field-wise equality and gets this backwards, so every
entity derives its equality from here instead.
"""

from abc import ABC
from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(eq=False, kw_only=True)
class Entity[TKey](ABC):
    """An object with a lifecycle and an identity of type ``TKey``."""

    id: TKey

    def __eq__(self, other: object) -> bool:
        # Concrete type is part of identity: a User and a Tenant that happen
        # to share a UUID are different things.
        if not isinstance(other, Entity) or type(other) is not type(self):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))


@dataclass(eq=False, kw_only=True)
class UuidEntity(Entity[UUID]):
    """The default: a UUID-keyed entity that can mint its own identity.

    Subclasses must declare ``@dataclass(eq=False, kw_only=True)`` too —
    ``eq=False`` so the identity equality above survives, and ``kw_only``
    because ``id`` carries a default that would otherwise forbid every
    non-default field a subclass adds.
    """

    id: UUID = field(default_factory=uuid4)
