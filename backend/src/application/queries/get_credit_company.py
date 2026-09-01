"""Read one credit company."""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import CreditCompanyData
from domain.entities import CreditCompany
from infrastructure.persistence.tenant.models import CreditCompanyModel


class GetCreditCompanyQuery(Query[ResultWithData[CreditCompanyData]]):
    credit_company_id: UUID


class GetCreditCompanyHandler(
    IRequestHandler[ResultWithData[CreditCompanyData], GetCreditCompanyQuery]
):
    def __init__(
        self, companies: TenantDbRepository[CreditCompany, CreditCompanyModel]
    ) -> None:
        self._companies = companies

    async def handle(
        self, request: GetCreditCompanyQuery
    ) -> ResultWithData[CreditCompanyData]:
        company = await self._companies.get(request.credit_company_id)
        if company is None:
            raise NotFoundError(
                "no such credit company in this store",
                key="not_found",
                subject_key="credit_company",
            )
        return ResultWithData[CreditCompanyData].succeed_with_data(
            CreditCompanyData.from_entity(company)
        )
