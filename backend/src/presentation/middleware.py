"""Cross-cutting HTTP middleware, registered once from ``create_app``."""

import time
import uuid

from fastapi import FastAPI, Request
from loguru import logger


def register_request_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def _log_request(request: Request, call_next):
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        with logger.contextualize(request_id=request_id):
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.bind(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client=request.client.host if request.client else None,
            ).info("request handled")
        response.headers["X-Request-ID"] = request_id
        return response
