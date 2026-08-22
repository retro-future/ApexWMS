"""Who finances this store's customers (FR-11.3).

Readable by a Seller, because the till has to offer the list when a
customer picks a financing partner at the counter.
"""

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import CreditCompanyData
from application.ports import CreditCompanyRepository


class ListCreditCompaniesQuery(PagedQuery[PagedResult[CreditCompanyData]]):
    search: str | None = None
    is_active: bool | None = None


class ListCreditCompaniesHandler(
    IRequestHandler[PagedResult[CreditCompanyData], ListCreditCompaniesQuery]
):
    def __init__(self, companies: CreditCompanyRepository) -> None:
        self._companies = companies

    async def handle(
        self, request: ListCreditCompaniesQuery
    ) -> PagedResult[CreditCompanyData]:
        companies, total = await self._companies.list_page(
            page=request.page,
            page_size=request.page_size,
            search=request.search,
            is_active=request.is_active,
        )
        return PagedResult[CreditCompanyData].succeed_with_data(
            data=[CreditCompanyData.from_entity(c) for c in companies],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
