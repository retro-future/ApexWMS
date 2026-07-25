"""Health endpoint (PRD §9, Observability): liveness plus master-DB
reachability and the live tenant-engine count."""

import httpx

from infrastructure.config import Settings
from presentation.app import create_app


async def test_health_reports_degraded_when_the_master_db_is_unreachable():
    app = create_app(
        Settings(master_db_url="postgresql+asyncpg://nobody:nobody@127.0.0.1:1/nothing")
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["master_db"] == "unreachable"
    assert body["version"]


async def test_health_reports_ok_against_a_real_master_db(client):
    resp = await client.get("/api/v1/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["master_db"] == "ok"
    assert body["live_tenant_engines"] == 0


async def test_health_counts_live_tenant_engines(client, create_tenant):
    tenant = await create_tenant()
    # Touching a tenant-scoped endpoint opens that tenant's engine.
    await client.get("/api/v1/settings/tenant", headers=tenant.auth)

    body = (await client.get("/api/v1/health")).json()
    assert body["live_tenant_engines"] == 1
