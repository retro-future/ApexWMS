"""FR-5.1: a Manager opens a return to a supplier.

Header only — no lines. Every line arrives by scan, because that is what
happens in a stockroom: somebody picks the defective handsets off the shelf
and pulls the trigger on each one.

The reason is stated up front rather than at confirm. A return of unsold
stock and a return of defective stock are packed differently and go back
under different paperwork, so the operator knows which they are doing
before they start scanning.
"""

from uuid import UUID, uuid4

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import SupplierReturnData
from application.ports import (
    Clock,
    TenantUnitOfWork,
)
from application.services import DocumentNumberer
from domain.entities import Location, Supplier, SupplierReturn
from domain.enums import DocumentStatus, DocumentType, SupplierReturnReason
from infrastructure.persistence.tenant.models import (
    LocationModel,
    SupplierModel,
    SupplierReturnModel,
)


class CreateSupplierReturnCommand(Command[ResultWithData[SupplierReturnData]]):
    supplier_id: UUID
    location_id: UUID
    reason: SupplierReturnReason
    note: str | None = None


class CreateSupplierReturnHandler(
    IRequestHandler[ResultWithData[SupplierReturnData], CreateSupplierReturnCommand]
):
    def __init__(
        self,
        returns: TenantDbRepository[SupplierReturn, SupplierReturnModel],
        suppliers: TenantDbRepository[Supplier, SupplierModel],
        locations: TenantDbRepository[Location, LocationModel],
        numberer: DocumentNumberer,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._returns = returns
        self._suppliers = suppliers
        self._locations = locations
        self._numberer = numberer
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CreateSupplierReturnCommand
    ) -> ResultWithData[SupplierReturnData]:
        await self._assert_parties_exist(request)

        document = SupplierReturn(
            id=uuid4(),
            number=await self._numberer.next(DocumentType.SUPPLIER_RETURN),
            status=DocumentStatus.DRAFT,
            supplier_id=request.supplier_id,
            location_id=request.location_id,
            reason=request.reason,
            note=request.note,
            created_by=self._current.user_id,
            created_at=self._clock.now(),
        )
        await self._returns.add(document)
        await self._uow.commit()

        return ResultWithData[SupplierReturnData].succeed_with_data(
            SupplierReturnData.from_entity(document)
        )

    async def _assert_parties_exist(self, request: CreateSupplierReturnCommand) -> None:
        if await self._suppliers.get(request.supplier_id) is None:
            raise NotFoundError(
                f"supplier {request.supplier_id} does not exist in this store"
            )
        if await self._locations.get(request.location_id) is None:
            raise NotFoundError(
                f"location {request.location_id} does not exist in this store"
            )
