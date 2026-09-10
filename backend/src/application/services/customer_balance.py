"""What a store-credit sale still owes (§4.7, FR-11.6, FR-4.9d).

``remaining = debt − Σ payments − Σ return relief``, and this module is the
one statement of it on the Python side. Nothing stores a balance — not on
the customer, not on the invoice — so every read recomputes, and two readers
that recomputed differently would disagree about whether a customer owes
anything.

The third term is the newest and the easiest to forget. A customer who
brings a phone back on a sale they are still paying off has their debt
reduced first and takes cash only for whatever is left over (FR-4.9d), so a
return relieves debt that no payment ever settled. Leave the term out and
``BalanceVerifier`` sees a balance larger than the truth, the debtor list
chases money nobody owes, and a further payment is accepted past what is
outstanding.

Only a **confirmed** return relieves anything: a draft has taken no goods
and paid nobody, and a cancelled one gave the relief back with the phone.
"""

from collections.abc import Iterable

from domain.entities import CustomerReturn, Payment, SalesInvoice
from domain.enums import DocumentStatus
from domain.value_objects import Currency, Money


def paid_on(payments: Iterable[Payment]) -> Money:
    """What has been paid *against the debt*, som, reversals netted.

    Non-som rows are skipped rather than converted: a debt is a som figure
    and a tender in another currency settles none of it (§4.5 rule 1).
    """
    total = Money.zero(Currency.UZS)
    for payment in payments:
        if payment.amount.currency is Currency.UZS:
            total = total + payment.amount
    return total


def relieved_on(returns: Iterable[CustomerReturn]) -> Money:
    """What confirmed returns have written off this sale's debt, som."""
    total = Money.zero(Currency.UZS)
    for document in returns:
        if document.status is not DocumentStatus.CONFIRMED:
            continue
        if document.debt_relief is not None:
            total = total + document.debt_relief
    return total


def remaining_on(
    invoice: SalesInvoice,
    payments: Iterable[Payment] = (),
    returns: Iterable[CustomerReturn] = (),
) -> Money:
    """What is still owed on this sale, never below zero.

    A cancelled sale's debt is void (FR-11.11), so it owes nothing whatever
    was paid against it — and the payments stay listed, because they are a
    refund somebody has to hand back.
    """
    if invoice.debt is None or invoice.status is not DocumentStatus.CONFIRMED:
        return Money.zero(Currency.UZS)
    owing = invoice.debt - paid_on(payments) - relieved_on(returns)
    return Money.zero(Currency.UZS) if owing.is_negative else owing
