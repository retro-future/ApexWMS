"""Infrastructure type aliases.

Two kinds of database exist (PRD §3.2):

    MasterDB — the single master database: tenants, users, memberships.
    TenantDB — one database per tenant, resolved per request.

Both are plain SQLAlchemy ``AsyncEngine`` / ``AsyncSession`` objects under
the hood; the ``NewType`` aliases give each its own identity in the DI
container, so a repository can ask for exactly the database it needs and
can never be handed the wrong one.
"""

from typing import NewType

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

MasterEngine = NewType("MasterEngine", AsyncEngine)
MasterSession = NewType("MasterSession", AsyncSession)

TenantEngine = NewType("TenantEngine", AsyncEngine)
TenantSession = NewType("TenantSession", AsyncSession)
