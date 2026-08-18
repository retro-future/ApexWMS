"""One endpoint for the scanner (PRD §6, §8, FR-7.1).

``Permission.Scan.Lookup`` sits in every tenant role's set — a Seller has
to be able to scan the phone a customer just put on the counter, and a
Storekeeper has to be able to ask what a code in the stockroom is. What
the answer *contains* is narrowed by ``Permission.Cost.View`` inside
``DeviceUnitData`` (FR-1.7), so the permission shapes the payload rather
than gating the route.

Lookup is a read and nothing else. Repricing a handset found this way is
``PATCH /device-units/{id}/price``, under the pricing permission.
"""

from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.core import ResultWithData
from application.dtos import CurrentUser
from application.models import ScanLookupData
from application.queries.scan_lookup import ScanLookupHandler, ScanLookupQuery
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/scan",
    tags=["stock"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("/lookup")
async def scan_lookup(
    query: Annotated[ScanLookupQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ScanLookupHandler],
) -> ResultWithData[ScanLookupData]:
    """FR-7.1: one call, and the answer states which kind of thing it found."""
    require(current, Permission.SCAN_LOOKUP)
    return await handler.handle(query)
