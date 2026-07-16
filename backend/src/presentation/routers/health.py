"""Health endpoint.

M0: liveness only. M1 extends this to report control-DB reachability and
the count of live tenant engines (PRD §9, Observability).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from version import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
