"""Domain errors.

Every rule violation inside the domain raises a subclass of DomainError.
The presentation layer maps these to HTTP responses; the domain knows
nothing about HTTP.
"""


class DomainError(Exception):
    """Base class for all domain rule violations."""


class InvalidMoneyError(DomainError):
    """Money constructed from something that is not an exact minor-unit amount."""


class CurrencyMismatchError(DomainError):
    """Arithmetic or comparison attempted across two different currencies."""


class InvalidIMEIError(DomainError):
    """A string that is not a structurally valid IMEI (length, digits, Luhn)."""


class InvalidSkuError(DomainError):
    """A string that cannot be a SKU (empty, too long, illegal characters)."""


class InvalidBarcodeError(DomainError):
    """Not a structurally valid EAN/UPC (length, digits, GS1 check digit)."""


class BarcodeNotAllowedError(DomainError):
    """A barcode on a SERIAL product — barcodes are for quantity items (FR-2.3)."""


class PriceNotSetError(DomainError):
    """A line resolved to no sale price at all (FR-2.14, §4.5b).

    Raised rather than falling back to the catalog, because the fallback is
    the signature bug of bolting used stock onto a new-goods catalog: a
    used handset worth $500 quoted at the model's new price of $900 shows
    no error, no empty field, and no visual cue — just a plausible number
    on an invoice and $600 of profit that never existed.
    """


class InvalidDeviceUnitError(DomainError):
    """A handset described in a way that cannot be true of a real one —
    on the shelf but nowhere, or sold and still holding a location."""


class UnitNotRepriceableError(DomainError):
    """A repricing aimed at a unit that has left the shelf (FR-2.16).

    Repricing a sold handset is meaningless and would corrupt its trace:
    the sale already snapshotted what it charged, so a later markdown could
    only make the history lie about what was on offer at the time.
    """


class InvalidMovementError(DomainError):
    """A stock movement that would record nothing (PRD §4.3).

    A zero delta is the case this exists for: the ledger records what
    changed, and a row asserting that nothing did is noise that every
    later reconciliation has to read past.
    """


class PriceCannotBeUnsetError(DomainError):
    """An attempt to clear a price that has already been set (FR-2.19, §4.5b).

    A price is the projection of an append-only log, and the log has no row
    shape meaning "no longer priced" — so clearing one would leave the
    projection contradicting the history it is supposed to be derived from.
    A model the store has stopped selling is deactivated, not un-priced.
    """
