"""Application/domain error → HTTP status mapping.

Registered as FastAPI exception handlers; raised errors from use cases
(and from DI resolution, e.g. a missing bearer token) surface here.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from application.errors import (
    AlreadyMemberError,
    ApplicationError,
    AuthenticationError,
    AuthorizationError,
    BarcodeAlreadySetError,
    BarcodeGenerationError,
    DuplicateBarcodeError,
    DuplicateImeiError,
    DuplicateNameError,
    DuplicateSkuError,
    InvalidLogoError,
    InvalidSlugError,
    InvalidTimezoneError,
    InvitationError,
    LastOwnerError,
    MissingTenantError,
    NotFoundError,
    ProvisioningFailedError,
    SkuGenerationError,
    SlugAlreadyTakenError,
    TenantNotActiveError,
    TenantNotFoundError,
)
from application.localization.catalog import MessageCatalog
from application.localization.locale import Locale
from domain.errors import (
    AlreadyReturnedError,
    CountAlreadyClosedError,
    CountNotClosedError,
    DebtReliefError,
    DocumentNotConfirmedError,
    DocumentNotDraftError,
    DomainError,
    DuplicateScanError,
    InsufficientStockError,
    InvoiceHasReturnsError,
    NotACreditSaleError,
    OverpaymentError,
    OverReceiptError,
    PaymentAlreadyReversedError,
    PriceNotSetError,
    RefundExceedsChargeError,
    TenderAlreadyRecordedError,
    TenderExceedsSaleError,
    UnitNotFromSupplierError,
    UnitNotRemovableError,
    UnitNotReturnableError,
    UnitNotSellableError,
    WrongLocationError,
)

_STATUS: list[tuple[type[Exception], int]] = [
    # Order matters: subclasses before their bases.
    (AuthenticationError, 401),
    (AuthorizationError, 403),
    (TenantNotActiveError, 403),
    (NotFoundError, 404),
    (TenantNotFoundError, 404),
    (AlreadyMemberError, 409),
    (LastOwnerError, 409),
    (SlugAlreadyTakenError, 409),
    (DuplicateSkuError, 409),
    (DuplicateBarcodeError, 409),
    (DuplicateNameError, 409),
    (DuplicateImeiError, 409),
    (SkuGenerationError, 409),
    (BarcodeGenerationError, 409),
    (BarcodeAlreadySetError, 409),
    # A document in the wrong state is a conflict, not bad input: the
    # same request would have succeeded a moment earlier (§4.4).
    (DocumentNotDraftError, 409),
    (DocumentNotConfirmedError, 409),
    (OverReceiptError, 409),
    (DuplicateScanError, 409),
    # So is a handset that cannot be sold, and for the same reason: the
    # goods, not the request, are what changed (§5.4). A handset that cannot
    # be returned or written off is the same thing seen from §5.5.
    (UnitNotSellableError, 409),
    (UnitNotRemovableError, 409),
    (UnitNotFromSupplierError, 409),
    (WrongLocationError, 409),
    # And a count whose close has or has not happened yet: the same request
    # would have succeeded on the other side of it (§5.6).
    (CountNotClosedError, 409),
    (CountAlreadyClosedError, 409),
    (InsufficientStockError, 409),
    (PriceNotSetError, 409),
    # And so is a payment the balance has moved out from under: paying
    # 500 000 against a debt somebody else just cleared is a conflict, not
    # a malformed request (§4.7). Terms that contradict each other are
    # bad input, so they fall through to ``DomainError`` and 422.
    (OverpaymentError, 409),
    (NotACreditSaleError, 409),
    (PaymentAlreadyReversedError, 409),
    (TenderAlreadyRecordedError, 409),
    (TenderExceedsSaleError, 409),
    # A customer return is the same shape of conflict throughout: goods
    # somebody else already took back, a sale that is no longer confirmed,
    # relief against a balance that has moved, or a refund the sale never
    # charged. Every one of them would have succeeded a moment earlier
    # (§5.4b). ``UnapprovedRefundError`` is deliberately not here — a
    # reduction sent without a note is a malformed request, not a race.
    (AlreadyReturnedError, 409),
    (UnitNotReturnableError, 409),
    (RefundExceedsChargeError, 409),
    (DebtReliefError, 409),
    (InvoiceHasReturnsError, 409),
    (MissingTenantError, 400),
    (InvitationError, 400),
    (InvalidTimezoneError, 422),
    (InvalidSlugError, 422),
    (InvalidLogoError, 422),
    (ProvisioningFailedError, 500),
    (ApplicationError, 400),
    (DomainError, 422),
]


def _status_for(exc: Exception) -> int:
    for exc_type, status in _STATUS:
        if isinstance(exc, exc_type):
            return status
    return 500


_catalog = MessageCatalog()


async def _handle(request: Request, exc: Exception) -> JSONResponse:
    status = _status_for(exc)
    locale = Locale.parse(request.headers.get("accept-language"))
    key = getattr(exc, "message_key", None) or getattr(exc, "code", None)
    params = dict(getattr(exc, "params", {}))
    subject_key = params.pop("subject_key", None)
    if isinstance(subject_key, str):
        params["subject"] = (
            _catalog.render(locale, "nouns", subject_key) or subject_key
        )
    detail = (
        _catalog.render(locale, "errors", key, **params) if isinstance(key, str) else None
    )
    detail = detail or str(exc) or exc.__class__.__name__
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(status_code=status, content={"detail": detail}, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, _handle)
    app.add_exception_handler(DomainError, _handle)
