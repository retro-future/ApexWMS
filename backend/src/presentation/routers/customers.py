"""Who this store sells to (PRD §8): Seller and up.

``Permission.Customer.*`` belongs to the Seller set (and so to Manager and
Owner) but not to the Storekeeper: someone receiving cartons has no reason
to read the customer list.

The account route takes a separate permission, ``CustomerAccount.View``,
because what somebody owes is a different question from who they are —
and the *whole* debtor list takes a different one again
(``CustomerAccount.ViewAll``, on the reports router), since that is a
business-health figure rather than a serving-this-customer one.
"""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.commands.create_customer import CreateCustomerCommand, CreateCustomerHandler
from application.commands.update_customer import UpdateCustomerCommand, UpdateCustomerHandler
from application.core import PagedResult, ResultWithData
from application.dtos import CurrentUser
from application.models import CustomerAccountData, CustomerData
from application.queries.get_customer import GetCustomerHandler, GetCustomerQuery
from application.queries.get_customer_account import (
    GetCustomerAccountHandler,
    GetCustomerAccountQuery,
)
from application.queries.list_customers import ListCustomersHandler, ListCustomersQuery
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/customers",
    tags=["catalog"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("")
async def list_customers(
    query: Annotated[ListCustomersQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListCustomersHandler],
) -> PagedResult[CustomerData]:
    require(current, Permission.CUSTOMER_VIEW)
    return await handler.handle(query)


@router.post("", status_code=201)
async def create_customer(
    body: CreateCustomerCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CreateCustomerHandler],
) -> ResultWithData[CustomerData]:
    require(current, Permission.CUSTOMER_MANAGE)
    return await handler.handle(body)


@router.get("/{customer_id}")
async def get_customer(
    customer_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetCustomerHandler],
) -> ResultWithData[CustomerData]:
    require(current, Permission.CUSTOMER_VIEW)
    return await handler.handle(GetCustomerQuery(customer_id=customer_id))


@router.get("/{customer_id}/account")
async def get_customer_account(
    customer_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetCustomerAccountHandler],
) -> ResultWithData[CustomerAccountData]:
    """FR-11.9: open debts with what is left on each, plus their financed
    sales labelled by company and carrying no balance at all."""
    require(current, Permission.CUSTOMER_ACCOUNT_VIEW)
    return await handler.handle(GetCustomerAccountQuery(customer_id=customer_id))


@router.patch("/{customer_id}")
async def update_customer(
    customer_id: UUID,
    body: UpdateCustomerCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UpdateCustomerHandler],
) -> ResultWithData[CustomerData]:
    require(current, Permission.CUSTOMER_MANAGE)
    return await handler.handle(body.model_copy(update={"customer_id": customer_id}))
