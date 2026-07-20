"""MasterDB repositories — row ↔ entity mapping stays inside (PRD §7.3).

Each repository extends ``MasterCrudRepository`` with its aggregate's
entity, key, and model types; only queries with no generic shape (email
lookup, owner count, bulk revocation) are written out here.
"""

from .base import MasterCrudRepository
from .invitation import SqlInvitationRepository
from .membership import SqlMembershipRepository
from .refresh_token import SqlRefreshTokenRepository
from .tenant import SqlTenantRepository
from .user import SqlUserRepository

__all__ = [
    "MasterCrudRepository",
    "SqlInvitationRepository",
    "SqlMembershipRepository",
    "SqlRefreshTokenRepository",
    "SqlTenantRepository",
    "SqlUserRepository",
]
