"""Read one credit company."""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import CreditCompanyData
from application.ports import CreditCompanyRepository


class GetCreditCompanyQuery(Query[ResultWithData[CreditCompanyData]]):
    credit_company_id: UUID


class GetCreditCompanyHandler(
    IRequestHandler[ResultWithData[CreditCompanyData], GetCreditCompanyQuery]
):
    def __init__(self, companies: CreditCompanyRepository) -> None:
        self._companies = companies

    async def handle(
        self, request: GetCreditCompanyQuery
    ) -> ResultWithData[CreditCompanyData]:
        company = await self._companies.get(request.credit_company_id)
        if company is None:
            raise NotFoundError("no such credit company in this store")
        return ResultWithData[CreditCompanyData].succeed_with_data(
            CreditCompanyData.from_entity(company)
        )
