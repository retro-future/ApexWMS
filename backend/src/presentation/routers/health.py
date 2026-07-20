"""Health endpoint (PRD §9, Observability): liveness, master-DB
reachability, and the count of live tenant engines."""


from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from infrastructure.tenancy import TenantEngineRegistry
from infrastructure.types import MasterEngine
from version import __version__

router = APIRouter(tags=["health"], route_class=DishkaRoute)


class HealthResponse(BaseModel):
    status: str
    version: str
    master_db: str
    live_tenant_engines: int


@router.get("/health", response_model=HealthResponse)
async def health(
    engine: FromDishka[MasterEngine],
    registry: FromDishka[TenantEngineRegistry],
) -> HealthResponse:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        master_db = "ok"
    except Exception:  # noqa: BLE001 - any failure means "unreachable"
        master_db = "unreachable"
    return HealthResponse(
        status="ok" if master_db == "ok" else "degraded",
        version=__version__,
        master_db=master_db,
        live_tenant_engines=registry.live_count,
    )
