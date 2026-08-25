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


class InvalidLineError(DomainError):
    """A document line whose shape could not describe a real transaction.

    A line for zero units, a serialized line naming no handset or claiming to
    sell two, a quantity line naming one anyway (§4.1). Distinct from
    ``InvalidMoneyError`` because the structure is what is wrong, not an
    amount — a line can be malformed while every figure on it is valid money.
    """


class DocumentNotDraftError(DomainError):
    """An edit or a confirm aimed at a document that is no longer a draft (§4.4).

    There is no "small correction" path on a confirmed document: it has
    already written rows into two append-only ledgers, and editing it would
    leave those ledgers describing something that no longer exists. The
    correction is a cancellation and a re-entry.
    """


class DocumentNotConfirmedError(DomainError):
    """A cancellation aimed at a document that was never confirmed (§4.4).

    Also what stops a document being reversed twice. ``LedgerPoster.reverse``
    deliberately has no such guard of its own — reversing a reversal would
    re-apply the original — so the document's own state is the one place
    that says a cancellation has already happened.
    """


class ReceiptSourceError(DomainError):
    """A Goods Receipt whose source and its parties disagree (FR-3.3b).

    ``SUPPLIER`` requires a supplier; ``TRADE_IN`` names none, and cannot
    be linked to a Purchase Order — there is no order for a phone that
    walked in the door.
    """


class ReceiptIncompleteError(DomainError):
    """A serial line confirmed with fewer scanned IMEIs than it declares (FR-3.8)."""


class DuplicateScanError(DomainError):
    """The same IMEI scanned twice onto one document (FR-3.5).

    Distinct from an IMEI that already exists elsewhere in the store, which
    needs a query and so is an application-level rule.
    """


class UnpricedUnitError(DomainError):
    """Goods about to enter stock with nothing saying what they are worth.

    Raised by a Goods Receipt confirmed while a unit lacks a cost or an
    asking price (FR-3.10), and by a Stock Count confirmed while a surplus
    has no value to book (FR-6.4b) — a surprise handset nobody has costed,
    or an accessory found at a location whose pool is empty. Names **every**
    offending IMEI or product in one message, so the gap is closed in one
    pass rather than discovered one item at a time.

    Unpriced used stock never reaches the shelf: the second guard, at the
    invoice line, exists because a unit can enter stock without a receipt at
    all.
    """


class UnpricedOrderLineError(DomainError):
    """A Purchase Order confirmed while a line still lacks a unit cost.

    Confirming a PO is the moment the deal with the supplier is final, so
    the price has to exist by then. A Goods Receipt can only be raised
    against a ``CONFIRMED`` order, which is what keeps an unpriced line from
    ever reaching a receipt.
    """


class OverReceiptError(DomainError):
    """A receipt would take a Purchase Order past what it ordered (FR-3.9).

    ``received_quantities`` only ever grows (a receipt, once confirmed, is
    never edited), so this is checked once at the point a new receipt is
    raised rather than re-derived at confirm time.
    """


class PriceCannotBeUnsetError(DomainError):
    """An attempt to clear a price that has already been set (FR-2.19, §4.5b).

    A price is the projection of an append-only log, and the log has no row
    shape meaning "no longer priced" — so clearing one would leave the
    projection contradicting the history it is supposed to be derived from.
    A model the store has stopped selling is deactivated, not un-priced.
    """


class UnitNotSellableError(DomainError):
    """A handset scanned onto an invoice that is not on the shelf (FR-4.3).

    States the status it actually holds. You cannot sell a phone that is
    already sold, and finding that out at the counter beats finding it out
    when the ledgers disagree.
    """


class WrongLocationError(DomainError):
    """A handset scanned onto an invoice raised for another location (FR-4.4).

    Stock is held somewhere specific, and a sale takes it from the place
    the invoice names — otherwise the movement would decrement a location
    the phone was never at.
    """


class InsufficientStockError(DomainError):
    """A line asking for more of an accessory than the location holds (FR-4.7).

    Refused whole: there is no partial fulfilment, because half a confirmed
    invoice is a document the ledgers could not describe.
    """


class EmptyInvoiceError(DomainError):
    """An invoice confirmed with no lines on it.

    Nothing left the store, so there is nothing to book — and a zero-line
    sale would still consume an invoice number and appear in every sales
    report as a transaction that never happened.
    """


class CreditTermsError(DomainError):
    """Payment terms that contradict the payment type (§4.7, FR-11.1).

    A cash sale naming a credit company, a financed sale carrying a som
    debt, a store-credit sale carrying none — each would leave the invoice
    asserting two different things about who owes the store money.
    """


class AnonymousDebtError(DomainError):
    """A store-credit sale that names no customer (§4.7).

    An invoice may be raised for a walk-in (FR-4.1), but a debt cannot: it
    would be money the store knows it is owed and cannot say by whom,
    invisible to every customer account and to the debtor list.
    """


class NotACreditSaleError(DomainError):
    """A payment recorded against a sale that opened no debt (FR-11.4).

    A cash sale and a financed one are both settled at confirm, so there is
    nothing for a payment to settle.
    """


class OverpaymentError(DomainError):
    """A payment larger than what is still owed (FR-11.6).

    ``remaining = debt − Σ payments`` is a projection of append-only rows,
    so a balance can only stay non-negative if the rows that build it are
    refused at the point they would break it.
    """


class PaymentAlreadyReversedError(DomainError):
    """A second compensating entry against one payment (FR-11.8).

    Reversing a reversal would re-apply the payment. The original stays in
    the ledger either way — a mistake is compensated, never deleted.
    """


class EmptyDocumentError(DomainError):
    """A supplier return or write-off confirmed with nothing on it (§5.5, §5.6).

    The outbound twin of ``EmptyInvoiceError``: no goods moved, so there is
    nothing to book, and the document would still burn a number and appear
    in the loss and return reports as an event that never happened.
    """


class UnitNotRemovableError(DomainError):
    """A handset sent back or written off that is not on the shelf (FR-5.2).

    States the status it actually holds. A phone already sold cannot also be
    returned to the supplier, and the ledger would have it leaving the store
    twice.
    """


class UnitNotFromSupplierError(DomainError):
    """A handset sent back to a supplier it never came from (FR-5.2b).

    Origin is proven by the goods receipt that put the unit in stock, so a
    trade-in and a handset a stock count discovered are refused too: neither
    can name a supplier at all.
    """


class CountNotClosedError(DomainError):
    """A stock count confirmed before its discrepancies were reported (FR-6.3).

    Closing is what freezes the three lists; confirming applies exactly what
    was reported. Without the close, the adjustments would be computed
    against a count still being scanned.
    """


class CountAlreadyClosedError(DomainError):
    """A scan or a count entered onto a count that has been closed (FR-6.3).

    The whole value of the close is that the discrepancy report and the
    adjustments describe the same shelf. A late scan would make them differ.
    """
