"""Cancelling a confirmed customer return (§4.4, FR-10.2, FR-4.9g).

**Compensation, never deletion.** The ``+`` movements, the
``SALES_RETURN_REFUND`` rows and the positive ``COGS`` rows all stay exactly
where they are, and ``LedgerPoster.reverse`` appends their negation. Each
handset is reprojected from its own timeline, which walks it back from
``IN_STOCK`` to ``SOLD`` — the status ``UnitProjector`` reaches through
``CUSTOMER_RETURN``'s entry in its map, for exactly this case.

The debt relief goes with it, and needs no compensating row: it is a column
on the return, and every balance read counts confirmed returns only. Same
discipline as the invoice's own ``debt``.

What this does *not* do is take the cash back off the customer. A refund
handed over and then called off is a conversation, and the ledger's job is
only to stop claiming the goods came back.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import CustomerReturnData
from application.ports import Clock, TenantUnitOfWork
from application.services import LedgerPoster
from application.specs import CustomerReturnForWrite
from domain.entities import CustomerReturn
from domain.enums import DocumentType
from infrastructure.persistence.tenant.models import CustomerReturnModel


class CancelCustomerReturnCommandPayload(CamelModel):
    reason: str | None = None


class CancelCustomerReturnCommand(
    CancelCustomerReturnCommandPayload, Command[ResultWithData[CustomerReturnData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    customer_return_id: UUID


class CancelCustomerReturnHandler(
    IRequestHandler[ResultWithData[CustomerReturnData], CancelCustomerReturnCommand]
):
    def __init__(
        self,
        returns: TenantDbRepository[CustomerReturn, CustomerReturnModel],
        poster: LedgerPoster,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._returns = returns
        self._poster = poster
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CancelCustomerReturnCommand
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

        document.cancel(self._clock.now(), self._current.user_id, request.reason)
        await self._poster.reverse(DocumentType.CUSTOMER_RETURN, document.id)
        await self._returns.update(document, spec)
        await self._uow.commit()

        return ResultWithData[CustomerReturnData].succeed_with_data(
            CustomerReturnData.from_entity(document)
        )
