"""FR-4.5, FR-4.5f, FR-4.5g: a Manager negotiates one line.

Selling a handset below its asking price is the same economic act as
marking the handset down, by an easier route — so it is recorded too. But
not as edit history: a draft line may be repriced any number of times and
none of it is kept (FR-4.5c). What is recorded is who approved the price
that survives, stamped **now** rather than at confirm, because the person
who approves a discount and the person who confirms the invoice need not
be the same. Without that, the ledger's ``user_id`` names the confirmer
and misattributes the decision.

An override touches this line and nothing else. It does not go through
``DeviceUnitRepricer`` and writes no ``device_unit_price_change`` — cancel
the invoice and the handset is back on the shelf asking what it always
asked.

The note is never mandatory, and there is no threshold and no approval
workflow (FR-4.5g). A field demanded on every small haggle becomes a dash
within a week and then means nothing. The system makes the deviation
visible; the owner decides what it means.

Sending ``price: null`` clears the override and hands the line back to
resolution, which is not the same as pricing it at zero — so the approver
and the note go with it.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import SalesInvoiceData
from application.ports import TenantUnitOfWork
from application.specs import SalesInvoiceForWrite
from domain.entities import SalesInvoice, SalesInvoiceLine
from domain.errors import InvalidMoneyError
from domain.value_objects import Money
from infrastructure.persistence.tenant.models import SalesInvoiceModel


class OverrideInvoiceLinePriceCommandPayload(CamelModel):
    # --- pricing-override permission only (FR-4.5) ---
    # Never a float: a fractional JSON number would be a rounding decision
    # nobody made. ``None`` clears the override.
    price: str | int | None = None
    note: str | None = None
    # --- sales permission (FR-4.5c) ---
    quantity: int | None = None


class OverrideInvoiceLinePriceCommand(
    OverrideInvoiceLinePriceCommandPayload, Command[ResultWithData[SalesInvoiceData]]
):
    # URL path segments, filled in by the router — never sent by the client.
    sales_invoice_id: UUID
    line_id: UUID


class OverrideInvoiceLinePriceHandler(
    IRequestHandler[ResultWithData[SalesInvoiceData], OverrideInvoiceLinePriceCommand]
):
    def __init__(
        self,
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._invoices = invoices
        self._uow = uow
        self._current = current

    async def handle(
        self, request: OverrideInvoiceLinePriceCommand
    ) -> ResultWithData[SalesInvoiceData]:
        spec = SalesInvoiceForWrite(request.sales_invoice_id)
        invoice = await self._invoices.find_one(spec)
        if invoice is None:
            raise NotFoundError(
                f"invoice {request.sales_invoice_id} does not exist in this store",
                key="not_found",
                subject_key="invoice",
            )
        invoice.assert_editable()
        line = self._target_line(invoice.lines, request.line_id, invoice.number)

        sent = request.model_fields_set
        if "quantity" in sent:
            self._set_quantity(line, request.quantity)
        if "price" in sent or "note" in sent:
            line.override(
                self._money(request.price, line),
                self._current.user_id,
                request.note,
            )

        await self._invoices.update(invoice, spec)
        await self._uow.commit()

        return ResultWithData[SalesInvoiceData].succeed_with_data(
            SalesInvoiceData.from_entity(invoice)
        )

    @staticmethod
    def _target_line(
        lines: list[SalesInvoiceLine], line_id: UUID, number: str
    ) -> SalesInvoiceLine:
        line = next((one for one in lines if one.id == line_id), None)
        if line is None:
            raise NotFoundError(f"{number} has no line {line_id}", key="not_found_line")
        return line

    @staticmethod
    def _set_quantity(line: SalesInvoiceLine, quantity: int | None) -> None:
        """Only an accessory has a quantity to change (§4.1)."""
        if line.is_serial:
            raise InvalidMoneyError(
                "a serialized line sells one named handset — remove it and scan "
                "another IMEI to sell a second"
            )
        if quantity is None or quantity <= 0:
            raise InvalidMoneyError("a line for zero units sells nothing")
        line.quantity = quantity

    @staticmethod
    def _money(amount: str | int | None, line: SalesInvoiceLine) -> Money | None:
        """The currency is the product's, never the caller's (§4.5 rule 3)."""
        return None if amount is None else Money.from_major(amount, line.currency)
