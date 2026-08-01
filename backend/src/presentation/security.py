"""Authorization checks (FR-1.6): permissions, not role names.

The §2.1 matrix is not hierarchical — a Storekeeper receives goods but
cannot sell, a Seller sells but cannot receive — so there is no rank to
compare. A route names the permission it needs and the caller either holds
it or does not, whether it came from a tenant role or a platform one.
"""

from fastapi.security import HTTPBearer

from application.dtos import CurrentUser
from application.errors import AuthorizationError
from domain.permissions import Permission

# Declares the bearer scheme in the OpenAPI schema so Swagger UI shows an
# "Authorize" button on the routers that depend on it. Cosmetic only: the
# actual token is read straight off the header by ``RequestBearerClaims``
# regardless of this dependency, so it must never raise — a missing/absent
# token still reaches the handler and comes out as 401 from there.
bearer_scheme = HTTPBearer(auto_error=False)


def require(user: CurrentUser, *permissions: Permission) -> None:
    """Every named permission must be held. Raises 403 otherwise."""
    missing = [p for p in permissions if p not in user.permissions]
    if missing:
        raise AuthorizationError(
            f"missing permission: {', '.join(sorted(missing))}"
        )


def require_any(user: CurrentUser, *permissions: Permission) -> None:
    """At least one of the named permissions must be held."""
    if not any(p in user.permissions for p in permissions):
        raise AuthorizationError(
            f"requires one of: {', '.join(sorted(permissions))}"
        )
