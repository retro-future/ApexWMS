"""Undoing a payment (PRD §8, FR-11.8).

One route, and it lives here rather than under ``/invoices`` because a
payment is reversed by its own id: the person correcting the mistake is
looking at the payment, not hunting for the sale it belongs to.

Recording a payment is the other way round — it is an act against an open
invoice, so ``POST /invoices/{id}/payments`` lives on the invoice router.

``Payment.Reverse`` is Manager and Owner while ``Payment.Record`` reaches
a Seller (§2.1): taking money is the counter's job, and unwinding it is
not.
"""

from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends

from application.commands.reverse_payment import (
    ReversePaymentCommand,
    ReversePaymentHandler,
)
from application.core import ResultWithData
from application.dtos import CurrentUser
from application.models import SalesInvoiceData
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/payments",
    tags=["credit"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.post("/{payment_id}/reverse")
async def reverse_payment(
    payment_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ReversePaymentHandler],
) -> ResultWithData[SalesInvoiceData]:
    """FR-11.8: a compensating negative payment. The original stays."""
    require(current, Permission.PAYMENT_REVERSE)
    return await handler.handle(ReversePaymentCommand(payment_id=payment_id))
