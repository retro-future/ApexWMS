"""FR-11.3: an Owner adds a financing partner.

Names are unique within the store, so "which sales went through Uzum?" is
a question with one answer.
"""

from uuid import uuid4

from pydantic import EmailStr

from application.common.repository import TenantDbRepository
from application.common.specification import Specification
from application.core import Command, IRequestHandler, ResultWithData
from application.errors import DuplicateNameError
from application.models import CreditCompanyData
from application.ports import Clock, TenantUnitOfWork
from domain.entities import CreditCompany
from infrastructure.persistence.tenant.models import CreditCompanyModel


class CreateCreditCompanyCommand(Command[ResultWithData[CreditCompanyData]]):
    name: str
    contact_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None


class CreateCreditCompanyHandler(
    IRequestHandler[ResultWithData[CreditCompanyData], CreateCreditCompanyCommand]
):
    def __init__(
        self,
        companies: TenantDbRepository[CreditCompany, CreditCompanyModel],
        clock: Clock,
        uow: TenantUnitOfWork,
    ) -> None:
        self._companies = companies
        self._clock = clock
        self._uow = uow

    async def handle(
        self, request: CreateCreditCompanyCommand
    ) -> ResultWithData[CreditCompanyData]:
        name = request.name.strip()
        if await self._companies.exists(
            Specification(CreditCompanyModel).where(CreditCompanyModel.name == name)
        ):
            raise DuplicateNameError(
            f"a credit company called {name!r} already exists",
            subject_key="credit_company",
            name=name,
        )

        company = CreditCompany(
            id=uuid4(),
            name=name,
            contact_name=request.contact_name,
            phone=request.phone,
            email=request.email,
            is_active=True,
            created_at=self._clock.now(),
        )
        await self._companies.add(company)
        await self._uow.commit()
        return ResultWithData[CreditCompanyData].succeed_with_data(
            CreditCompanyData.from_entity(company)
        )
