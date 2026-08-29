"""Edit or deactivate a credit company (FR-11.3).

Never a delete: sales already name the company that financed them, and
that history has to survive the partner going away. Contact details are
nullable, so they are cleared only when the caller explicitly sends
``null``.
"""

from uuid import UUID

from pydantic import EmailStr

from application.common.repository import TenantDbRepository
from application.common.specification import Specification
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.errors import DuplicateNameError, NotFoundError
from application.models import CreditCompanyData
from application.ports import TenantUnitOfWork
from application.specs import CreditCompanyForWrite
from domain.entities import CreditCompany
from infrastructure.persistence.tenant.models import CreditCompanyModel


class UpdateCreditCompanyCommandPayload(CamelModel):
    name: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    is_active: bool | None = None


class UpdateCreditCompanyCommand(
    UpdateCreditCompanyCommandPayload, Command[ResultWithData[CreditCompanyData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    credit_company_id: UUID


class UpdateCreditCompanyHandler(
    IRequestHandler[ResultWithData[CreditCompanyData], UpdateCreditCompanyCommand]
):
    def __init__(
        self,
        companies: TenantDbRepository[CreditCompany, CreditCompanyModel],
        uow: TenantUnitOfWork,
    ) -> None:
        self._companies = companies
        self._uow = uow

    async def handle(
        self, request: UpdateCreditCompanyCommand
    ) -> ResultWithData[CreditCompanyData]:
        company = await self._companies.find_one(
            CreditCompanyForWrite(request.credit_company_id)
        )
        if company is None:
            raise NotFoundError("no such credit company in this store")

        sent = request.model_fields_set
        if request.name is not None:
            name = request.name.strip()
            taken = Specification(CreditCompanyModel).where(
                CreditCompanyModel.name == name, CreditCompanyModel.id != company.id
            )
            if await self._companies.exists(taken):
                raise DuplicateNameError(
                    f"a credit company called {name!r} already exists"
                )
            company.name = name
        if request.is_active is not None:
            company.is_active = request.is_active
        if "contact_name" in sent:
            company.contact_name = request.contact_name
        if "phone" in sent:
            company.phone = request.phone
        if "email" in sent:
            company.email = request.email

        await self._companies.update(company)
        await self._uow.commit()
        return ResultWithData[CreditCompanyData].succeed_with_data(
            CreditCompanyData.from_entity(company)
        )
