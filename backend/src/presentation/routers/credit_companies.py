"""The financing partners this store sells through (PRD §8, FR-11.3).

The permission split is unusually wide on purpose (§2.1): **only an Owner
maintains the list**, but a Seller has to read it, because picking the
company is part of closing a financed sale at the counter.
"""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.commands.create_credit_company import (
    CreateCreditCompanyCommand,
    CreateCreditCompanyHandler,
)
from application.commands.update_credit_company import (
    UpdateCreditCompanyCommand,
    UpdateCreditCompanyCommandPayload,
    UpdateCreditCompanyHandler,
)
from application.core import PagedResult, ResultWithData
from application.dtos import CurrentUser
from application.models import CreditCompanyData
from application.queries.get_credit_company import (
    GetCreditCompanyHandler,
    GetCreditCompanyQuery,
)
from application.queries.list_credit_companies import (
    ListCreditCompaniesHandler,
    ListCreditCompaniesQuery,
)
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/credit-companies",
    tags=["credit"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("")
async def list_credit_companies(
    query: Annotated[ListCreditCompaniesQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListCreditCompaniesHandler],
) -> PagedResult[CreditCompanyData]:
    require(current, Permission.CREDIT_COMPANY_VIEW)
    return await handler.handle(query)


@router.post("", status_code=201)
async def create_credit_company(
    body: CreateCreditCompanyCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CreateCreditCompanyHandler],
) -> ResultWithData[CreditCompanyData]:
    require(current, Permission.CREDIT_COMPANY_MANAGE)
    return await handler.handle(body)


@router.get("/{credit_company_id}")
async def get_credit_company(
    credit_company_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetCreditCompanyHandler],
) -> ResultWithData[CreditCompanyData]:
    require(current, Permission.CREDIT_COMPANY_VIEW)
    return await handler.handle(
        GetCreditCompanyQuery(credit_company_id=credit_company_id)
    )


@router.patch("/{credit_company_id}")
async def update_credit_company(
    credit_company_id: UUID,
    body: UpdateCreditCompanyCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UpdateCreditCompanyHandler],
) -> ResultWithData[CreditCompanyData]:
    """Deactivating is how a partner goes away — never a delete, because
    every sale they financed still names them."""
    require(current, Permission.CREDIT_COMPANY_MANAGE)
    return await handler.handle(
        UpdateCreditCompanyCommand(
            **body.model_dump(exclude_unset=True),
            credit_company_id=credit_company_id,
        )
    )
