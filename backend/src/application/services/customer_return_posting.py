"""Goods coming back from a customer, and the money going back (PRD §5.4b).

The inbound mirror of ``RemovalPoster``, and it books two money rows per
line rather than one, because a sale has two sides. The refund goes out
under ``SALES_RETURN_REFUND`` at the price the return states; the cost comes
back under a **positive** ``COGS`` at what the sale originally booked.

That second row is not a stylistic choice. ``CostPoolReader`` rebuilds an
accessory's pool by pairing each positive movement with the money rows on
the same ``document_id`` whose ``INVENTORY_SIGN`` contribution is positive,
and ``COGS`` is already ``+1`` there. So returned accessories re-enter the
pool at the value they left it, and ``verify-financials`` and the month-end
rollforward fold the same figure without either learning a new category.

Per line, in this order and for a reason:

1. The goods are re-checked against the live store. A handset has to still
   be ``SOLD`` and to have been sold on the invoice this return names — a
   draft reserves nothing, and neither fact is safe to trust from the scan.
2. The line is valued at what the *sale* carried it at: a phone's own
   ``acquisition_cost``, or an accessory line's share of the COGS that
   invoice actually booked. Never the current pool average, which would let
   goods re-enter at a value nobody ever paid for them.
3. Both ledgers are written by ``LedgerPoster``, together or not at all.

Nothing here commits. The handler owns the transaction.
"""

from collections.abc import Sequence
from uuid import UUID

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.dtos import MoneyEffect, Posting, PostingEntry
from application.errors import NotFoundError
from application.services.ledger import LedgerPoster
from application.specs import DeviceUnitById, TransactionsForDocument
from domain.entities import (
    CustomerReturn,
    CustomerReturnLine,
    DeviceUnit,
    FinancialTransaction,
    SalesInvoice,
)
from domain.enums import DeviceStatus, DocumentType, MovementType, TransactionType
from domain.errors import UnitNotReturnableError
from domain.value_objects import Money
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    FinancialTransactionModel,
)


class CustomerReturnPoster:
    def __init__(
        self,
        units: TenantDbRepository[DeviceUnit, DeviceUnitModel],
        transactions: TenantAppendOnlyRepository[
            FinancialTransaction, FinancialTransactionModel
        ],
        poster: LedgerPoster,
    ) -> None:
        self._units = units
        self._transactions = transactions
        self._poster = poster

    async def take_back(
        self,
        document: CustomerReturn,
        invoice: SalesInvoice,
        prior_returns: Sequence[CustomerReturn] = (),
    ) -> None:
        """FR-4.9f: goods return to the shelf and the customer is paid back.

        *prior_returns* is every already-confirmed return against the same
        sale. An accessory line is valued as the difference between the
        cumulative share for everything returned so far and the share for
        everything returned before it, so N partial returns of one invoice
        line give back exactly the cost the sale booked and not a rounded
        minor unit more.
        """
        cogs = await self._invoice_cogs(invoice)
        entries: list[PostingEntry] = []
        for line in document.lines:
            money = [
                MoneyEffect(
                    TransactionType.COGS,
                    await self._cost_back(document, line, cogs, prior_returns),
                )
            ]
            # A line refunding nothing books no refund row. The goods still
            # come back; the money ledger refuses a zero amount, and a
            # kept-in-full restocking fee is a real case (FR-4.9c).
            if not line.line_total.is_zero:
                refund = TransactionType.SALES_RETURN_REFUND
                money.insert(
                    0, MoneyEffect(refund, line.line_total * refund.ordinary_sign)
                )
            entries.append(
                PostingEntry(
                    movement_type=MovementType.CUSTOMER_RETURN,
                    product_id=line.product_id,
                    location_id=document.location_id,
                    quantity_delta=line.quantity,
                    device_unit_id=line.device_unit_id,
                    # Stated rather than inferred: only the document knows
                    # that a ``+1`` here means a customer brought it back
                    # (§4.3).
                    new_status=DeviceStatus.IN_STOCK if line.is_serial else None,
                    new_location_id=document.location_id,
                    money=money,
                )
            )

        await self._poster.post(
            Posting(
                document_type=DocumentType.CUSTOMER_RETURN,
                document_id=document.id,
                entries=entries,
            )
        )

    async def _invoice_cogs(self, invoice: SalesInvoice) -> dict[UUID, Money]:
        """What the sale booked as cost, per accessory product.

        Read once for the whole document rather than per line: it is one
        query, and a return of three accessory lines would otherwise repeat
        it three times. Serialized lines are absent because their cost is on
        the unit, not in this map.
        """
        booked: dict[UUID, Money] = {}
        for txn in await self._transactions.find(
            TransactionsForDocument(DocumentType.SALES_INVOICE, invoice.id)
        ):
            if txn.txn_type is not TransactionType.COGS or txn.product_id is None:
                continue
            if txn.device_unit_id is not None:
                continue
            running = booked.get(txn.product_id)
            booked[txn.product_id] = txn.amount if running is None else running + txn.amount
        return booked

    async def _cost_back(
        self,
        document: CustomerReturn,
        line: CustomerReturnLine,
        cogs: dict[UUID, Money],
        prior_returns: Sequence[CustomerReturn],
    ) -> Money:
        """What this line puts back on the shelf, signed as inventory in.

        The sale booked ``COGS`` negative, so negating the share it is
        undoing is what makes the pair net to zero for a fully returned
        line. Valued as ``share(taken so far) − share(taken before)`` so the
        shares telescope: the last return of a line always gets the exact
        remainder, never a rounded one.
        """
        if line.is_serial:
            unit = await self._live_unit(document, line)
            return unit.acquisition_cost
        booked = cogs.get(line.product_id)
        if booked is None:
            raise NotFoundError(
                f"{document.number} returns {line.quantity} of a product the sale "
                "booked no cost for",
                key="not_found",
                subject_key="product",
            )
        before = sum(
            other_line.quantity
            for other in prior_returns
            for other_line in other.lines
            if other_line.sales_invoice_line_id == line.sales_invoice_line_id
            and not other_line.is_serial
        )
        undone = booked.share(before + line.quantity, line.sold_quantity)
        already = booked.share(before, line.sold_quantity)
        return already - undone

    async def _live_unit(
        self, document: CustomerReturn, line: CustomerReturnLine
    ) -> DeviceUnit:
        assert line.device_unit_id is not None
        unit = await self._units.find_one(DeviceUnitById(line.device_unit_id))
        if unit is None:
            raise NotFoundError(
                f"handset {line.device_unit_id} does not exist in this store",
                key="not_found",
                subject_key="device_unit",
            )
        # Re-checked at confirm because a draft reserves nothing (§4.4). A
        # phone already back on the shelf would otherwise arrive twice.
        if unit.status is not DeviceStatus.SOLD:
            raise UnitNotReturnableError(
                f"IMEI {unit.imei} is {unit.status.value}, not sold, so "
                f"{document.number} cannot take it back",
                imei=str(unit.imei),
                status=unit.status.value,
                number=document.number,
            )
        return unit
