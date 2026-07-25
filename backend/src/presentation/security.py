"""Authorization checks (FR-1.6): permissions, not role names.

The §2.1 matrix is not hierarchical — a Storekeeper receives goods but
cannot sell, a Seller sells but cannot receive — so there is no rank to
compare. A route names the permission it needs and the caller either holds
it or does not, whether it came from a tenant role or a platform one.
"""

from application.dtos import CurrentUser
from application.errors import AuthorizationError


def require(user: CurrentUser, *permissions: str) -> None:
    """Every named permission must be held. Raises 403 otherwise."""
    missing = [p for p in permissions if p not in user.permissions]
    if missing:
        raise AuthorizationError(
            f"missing permission: {', '.join(sorted(missing))}"
        )


def require_any(user: CurrentUser, *permissions: str) -> None:
    """At least one of the named permissions must be held."""
    if not any(p in user.permissions for p in permissions):
        raise AuthorizationError(
            f"requires one of: {', '.join(sorted(permissions))}"
        )
