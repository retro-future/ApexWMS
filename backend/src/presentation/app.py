"""FastAPI application factory."""

from contextlib import asynccontextmanager

from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from di import create_container
from infrastructure.config import Settings
from presentation.errors import register_error_handlers
from presentation.routers import (
    auth,
    customers,
    device_units,
    goods_receipts,
    health,
    locations,
    products,
    purchase_orders,
    suppliers,
    users,
)
from presentation.routers import settings as settings_router

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    container = create_container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await container.close()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    setup_dishka(container, app)
    register_error_handlers(app)

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)
    app.include_router(settings_router.router, prefix=API_PREFIX)
    app.include_router(products.router, prefix=API_PREFIX)
    app.include_router(locations.router, prefix=API_PREFIX)
    app.include_router(suppliers.router, prefix=API_PREFIX)
    app.include_router(customers.router, prefix=API_PREFIX)
    app.include_router(device_units.router, prefix=API_PREFIX)
    app.include_router(purchase_orders.router, prefix=API_PREFIX)
    app.include_router(goods_receipts.router, prefix=API_PREFIX)
    return app
