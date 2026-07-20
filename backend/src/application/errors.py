"""Application-level errors.

These are use-case failures, not domain rule violations (those live in
``domain/errors.py``). The presentation layer maps each to an HTTP
status; nothing here knows HTTP exists.
"""


class ApplicationError(Exception):
    """Base class for use-case failures."""


class AuthenticationError(ApplicationError):
    """The request carries no valid identity (401)."""


class InvalidCredentialsError(AuthenticationError):
    """Email/password pair does not authenticate."""


class InvalidTokenError(AuthenticationError):
    """A malformed, expired, revoked, or reused token."""


class AuthorizationError(ApplicationError):
    """An authenticated user lacks permission for the operation (403)."""


class TenantNotActiveError(ApplicationError):
    """The tenant exists but is not in ACTIVE status (PRD §3.2)."""


class EmailAlreadyRegisteredError(ApplicationError):
    """Signup with an email that already has an account."""


class AlreadyMemberError(ApplicationError):
    """Inviting or adding a user who already belongs to the tenant."""


class InvitationError(ApplicationError):
    """An invitation that is unknown, expired, or already used."""


class LastOwnerError(ApplicationError):
    """Demoting the tenant's only Owner would lock everyone out."""


class NotFoundError(ApplicationError):
    """The referenced resource does not exist in this tenant's scope."""


class InvalidTimezoneError(ApplicationError):
    """Not an IANA timezone name."""


class ProvisioningFailedError(ApplicationError):
    """Tenant provisioning failed; the tenant row is left FAILED and retryable."""
