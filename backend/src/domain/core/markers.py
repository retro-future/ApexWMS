"""Which database an entity lives in (PRD §3).

Isolation is physical — a tenant's data is in its own database, not behind
a ``tenant_id`` filter. These markers make that split visible in the type
so "which database is this?" is answered by the class, not by the folder
the module happens to sit in.

Deliberately plain classes, not ``Protocol``s: an empty Protocol is
structurally satisfied by every object, so ``isinstance`` would answer True
for anything and the marker would carry no information at all.
"""


class MasterEntity:
    """Lives in the MasterDB: tenants, users, memberships, auth records."""

    __slots__ = ()


class TenantEntity:
    """Lives in one tenant's own database, alongside all its business data."""

    __slots__ = ()
