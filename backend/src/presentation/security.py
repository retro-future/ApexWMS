"""Role checks (FR-1.6): explicit allowed-role sets, because the
permission matrix (PRD §2.1) is not hierarchical."""

from application.dtos import CurrentUser
from application.errors import AuthorizationError
from domain.roles import Role


def require(user: CurrentUser, *allowed: Role) -> None:
    if user.role not in allowed:
        raise AuthorizationError(
            f"role '{user.role}' may not perform this operation"
        )
