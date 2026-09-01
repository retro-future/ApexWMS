"""Application-level errors.

These are use-case failures, not domain rule violations (those live in
``domain/errors.py``). The presentation layer maps each to an HTTP
status; nothing here knows HTTP exists.
"""


from typing import ClassVar


def _snake_case(name: str) -> str:
    out: list[str] = []
    for i, char in enumerate(name):
        if char.isupper() and i and not name[i - 1].isupper():
            out.append("_")
        out.append(char.lower())
    return "".join(out)


class ApplicationError(Exception):
    """Base class for use-case failures.

    Each subclass gets a stable ``code`` (snake-cased class name without the
    ``Error`` suffix) that keys its message in the localization catalog. A
    raise site may pass ``**params`` for the template to interpolate; the
    positional ``message`` stays as the English fallback.
    """

    code: ClassVar[str] = "application"

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls.code = _snake_case(cls.__name__.removesuffix("Error"))

    def __init__(
        self, message: str = "", /, *, key: str | None = None, **params: object
    ) -> None:
        super().__init__(message)
        self.message_key: str = key or type(self).code
        self.params: dict[str, object] = params


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


class MissingTenantError(ApplicationError):
    """The request named no tenant — no bearer token and no X-Tenant-Slug (400)."""


class TenantNotFoundError(ApplicationError):
    """No tenant matches the supplied slug or id (404)."""


class SlugAlreadyTakenError(ApplicationError):
    """Another tenant already owns that slug."""


class InvalidSlugError(ApplicationError):
    """Not a usable tenant slug."""


class AlreadyMemberError(ApplicationError):
    """Inviting or adding a user who already belongs to the tenant."""


class InvitationError(ApplicationError):
    """An invitation that is unknown, expired, or already used."""


class LastOwnerError(ApplicationError):
    """Demoting the tenant's only Owner would lock everyone out."""


class NotFoundError(ApplicationError):
    """The referenced resource does not exist in this tenant's scope."""


class EntityNotPersistedError(ApplicationError):
    """``update`` was called for an entity that has no row.

    Not a ``NotFoundError``: that one is a caller asking for something that
    is not there, and it answers 404. This one means a handler mutated an
    entity it never loaded, which is a bug in the handler. It lives in
    ``application`` rather than ``domain`` because the domain knows nothing
    about persistence, and the refactor guide's rule 1 keeps it that way.
    """

    def __init__(self, model_name: str, entity_id: object) -> None:
        super().__init__(
            f"{model_name} {entity_id} has no persisted row",
            model_name=model_name,
            entity_id=entity_id,
        )
        self.model_name = model_name
        self.entity_id = entity_id


class InvalidTimezoneError(ApplicationError):
    """Not an IANA timezone name."""


class InvalidLogoError(ApplicationError):
    """The uploaded letterhead image is unusable (FR-8.1).

    Refused before it reaches the settings row, because the first thing to
    discover a bad image otherwise would be a PDF render, which is a
    download failing for whoever is standing at the counter.
    """


class DuplicateSkuError(ApplicationError):
    """Another product in this store already owns that SKU."""


class DuplicateBarcodeError(ApplicationError):
    """Another product in this store already owns that barcode (FR-2.3)."""


class SkuGenerationError(ApplicationError):
    """The SKU generator kept colliding with existing rows (509-style anomaly).

    A per-tenant counter that hits an occupied slot five times running is
    not routine retry territory; it means SKUs were assigned by hand in a
    way that shadows the sequence.
    """


class BarcodeGenerationError(ApplicationError):
    """The in-store barcode generator kept colliding with existing rows."""


class BarcodeAlreadySetError(ApplicationError):
    """Asked to generate a barcode for a product that already has one."""


class DuplicateNameError(ApplicationError):
    """Another location or supplier in this store already owns that name."""


class DuplicateImeiError(ApplicationError):
    """This store already holds a handset with that IMEI (FR-3.5).

    An application error rather than a domain one because answering it
    needs a query: the receipt being scanned onto cannot see the rest of
    the store's stock. Never silently accepted — a duplicate IMEI is either
    a scanning mistake or a stolen-goods red flag, and the message names
    the existing unit's status and location so the operator can tell which
    while the phone is still in their hand.
    """


class ProvisioningFailedError(ApplicationError):
    """Tenant provisioning failed; the tenant row is left FAILED and retryable."""
