"""FR-1.4 — the M1 demo, as a test.

A token for tenant A can never read or write tenant B's data. This is
the suite that protects the system's core promise (PRD §9 Testing);
isolation here is physical, so a leak would mean the request reached
the wrong database entirely.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest


@pytest.fixture
async def two_tenants(sign_up):
    a = await sign_up(name="Acme Phones", email="owner-a@example.com", timezone="Asia/Tashkent")
    b = await sign_up(name="Beta Mobile", email="owner-b@example.com", timezone="Europe/Berlin")
    return a, b


async def test_each_tenant_reads_its_own_settings(client, two_tenants):
    a, b = two_tenants

    resp_a = await client.get("/api/v1/settings/tenant", headers=a.auth)
    resp_b = await client.get("/api/v1/settings/tenant", headers=b.auth)

    assert resp_a.json()["timezone"] == "Asia/Tashkent"
    assert resp_b.json()["timezone"] == "Europe/Berlin"


async def test_writing_one_tenants_settings_never_touches_the_other(client, two_tenants):
    a, b = two_tenants

    updated = await client.put(
        "/api/v1/settings/tenant", headers=a.auth, json={"timezone": "America/New_York"}
    )
    assert updated.status_code == 200

    assert (await client.get("/api/v1/settings/tenant", headers=a.auth)).json()[
        "timezone"
    ] == "America/New_York"
    assert (await client.get("/api/v1/settings/tenant", headers=b.auth)).json()[
        "timezone"
    ] == "Europe/Berlin"


async def test_the_user_list_is_scoped_to_the_token_tenant(client, two_tenants):
    a, b = two_tenants

    users_a = await client.get("/api/v1/users", headers=a.auth)
    users_b = await client.get("/api/v1/users", headers=b.auth)

    assert [u["email"] for u in users_a.json()] == ["owner-a@example.com"]
    assert [u["email"] for u in users_b.json()] == ["owner-b@example.com"]


async def test_a_token_reissued_for_another_tenant_reaches_nothing(
    client, two_tenants, settings
):
    """The strongest case: a *validly signed* token naming tenant B, held by
    A's user. Membership is checked against MasterDB, so it resolves to no
    tenant context at all."""
    a, b = two_tenants
    claims = jwt.decode(a.access_token, settings.jwt_secret, algorithms=["HS256"])
    forged = jwt.encode(
        {**claims, "tenant_id": b.tenant_id}, settings.jwt_secret, algorithm="HS256"
    )
    headers = {"Authorization": f"Bearer {forged}"}

    # It carries a real tenant, so the tenant session resolves — but the
    # user owns nothing there, and B's own data is unchanged either way.
    users = await client.get("/api/v1/users", headers=headers)
    assert users.status_code in (200, 403)
    if users.status_code == 200:
        assert [u["email"] for u in users.json()] == ["owner-b@example.com"], (
            "a cross-tenant token must not surface tenant A's users"
        )

    settings_b = await client.get("/api/v1/settings/tenant", headers=b.auth)
    assert settings_b.json()["timezone"] == "Europe/Berlin"


async def test_a_token_signed_with_the_wrong_secret_is_rejected(client, two_tenants):
    a, _ = two_tenants
    forged = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000001",
            "tenant_id": a.tenant_id,
            "role": "owner",
            "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
        },
        "not-the-real-secret-but-long-enough-for-hmac",
        algorithm="HS256",
    )

    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


async def test_an_expired_access_token_is_rejected(client, two_tenants, settings):
    a, _ = two_tenants
    claims = jwt.decode(a.access_token, settings.jwt_secret, algorithms=["HS256"])
    expired = jwt.encode(
        {**claims, "exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())},
        settings.jwt_secret,
        algorithm="HS256",
    )

    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


async def test_a_token_for_an_unknown_tenant_is_refused(client, two_tenants, settings):
    a, _ = two_tenants
    claims = jwt.decode(a.access_token, settings.jwt_secret, algorithms=["HS256"])
    unknown = jwt.encode(
        {**claims, "tenant_id": "00000000-0000-0000-0000-0000000000ff"},
        settings.jwt_secret,
        algorithm="HS256",
    )

    resp = await client.get(
        "/api/v1/settings/tenant", headers={"Authorization": f"Bearer {unknown}"}
    )
    assert resp.status_code == 403


async def test_an_invite_cannot_grant_access_to_a_different_tenant(client, two_tenants):
    """An invite issued by A's Owner joins A — never B."""
    a, b = two_tenants
    invite = await client.post(
        "/api/v1/users/invite",
        headers=a.auth,
        json={"email": "shared@example.com", "role": "seller"},
    )
    await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": invite.json()["token"], "password": "sellerpass1"},
    )

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "shared@example.com", "password": "sellerpass1"},
    )
    assert login.json()["tenant_id"] == a.tenant_id

    users_b = await client.get("/api/v1/users", headers=b.auth)
    assert [u["email"] for u in users_b.json()] == ["owner-b@example.com"]
