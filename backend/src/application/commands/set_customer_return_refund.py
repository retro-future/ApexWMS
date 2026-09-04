"""FR-4.9c: a Manager keeps part of what the customer paid.

An opened box, a scratched back, a missing charger — the goods come back
worth less than they went out, and the store keeps the difference. That is a
decision somebody makes, so this endpoint stamps who made it and refuses to
run without a note. The same discipline ``override_invoice_line_price``
applies to a discount, in the other direction.

The ceiling is the invoice line's own ``charged_price``: a refund may go
down to zero and never above what the sale took. Raising it back to the full
charge is the same call with the original amount, which clears nothing —
the approver and the note stay, because somebody still decided.

The quantity moves through here too, for the reason FR-4.5c gives on the
invoice: a screen that can correct a mis-scanned count without unscanning
and re-scanning three times is the difference between a usable counter and
an annoying one.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import CustomerReturnData
from application.ports import TenantUnitOfWork
from application.services import SalePriceParser
from application.specs import CustomerReturnForWrite
from domain.entities import CustomerReturn, CustomerReturnLine
from infrastructure.persistence.tenant.models import CustomerReturnModel


class SetCustomerReturnRefundCommandPayload(CamelModel):
    # --- pricing-override permission only (FR-4.9c) ---
    # Never a float: a fractional JSON number would be a rounding decision
    # nobody made.
    refund: str | int | None = None
    note: str | None = None
    # --- customer-return permission (FR-4.5c's twin) ---
    quantity: int | None = None


class SetCustomerReturnRefundCommand(
    SetCustomerReturnRefundCommandPayload, Command[ResultWithData[CustomerReturnData]]
):
    # URL path segments, filled in by the router — never sent by the client.
    customer_return_id: UUID
    line_id: UUID


class SetCustomerReturnRefundHandler(
    IRequestHandler[ResultWithData[CustomerReturnData], SetCustomerReturnRefundCommand]
):
    def __init__(
        self,
        returns: TenantDbRepository[CustomerReturn, CustomerReturnModel],
        prices: SalePriceParser,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._returns = returns
        self._prices = prices
        self._uow = uow
        self._current = current

    async def handle(
        self, request: SetCustomerReturnRefundCommand
    ) -> ResultWithData[CustomerReturnData]:
        spec = CustomerReturnForWrite(request.customer_return_id)
        document = await self._returns.find_one(spec)
        if document is None:
            raise NotFoundError(
                f"customer return {request.customer_return_id} does not exist in "
                "this store",
                key="not_found",
                subject_key="customer_return",
            )
        document.assert_editable()
        line = self._line_of(document, request.line_id)

        if request.quantity is not None:
            line.count(request.quantity)
        if request.refund is not None:
            refund = self._prices.parse(request.refund, line.currency)
            assert refund is not None  # parse only returns None for a None input
            line.reduce_to(refund, self._current.user_id, request.note or "")

        await self._returns.update(document, spec)
        await self._uow.commit()
        return ResultWithData[CustomerReturnData].succeed_with_data(
            CustomerReturnData.from_entity(document)
        )

    @staticmethod
    def _line_of(document: CustomerReturn, line_id: UUID) -> CustomerReturnLine:
        line = next((one for one in document.lines if one.id == line_id), None)
        if line is None:
            raise NotFoundError(
                f"{document.number} has no line {line_id}",
                key="not_found",
                subject_key="customer_return_line",
            )
        return line
