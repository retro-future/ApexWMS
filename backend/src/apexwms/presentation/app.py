"""FastAPI application factory."""

from contextlib import asynccontextmanager

from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from apexwms.infrastructure.config import Settings
from apexwms.presentation.di import create_container
from apexwms.presentation.routers import health

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

    app.include_router(health.router, prefix=API_PREFIX)
    return app
