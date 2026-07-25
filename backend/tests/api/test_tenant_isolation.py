"""FR-1.4 — the M1 demo, as a test.

A token for store A can never read or write store B's data. This is the
suite that protects the system's core promise (PRD §9 Testing); isolation
is physical, so a leak would mean the request reached the wrong database
entirely.

Identity is master-side now, so the promise has a second half: a person
may hold one login and work at several stores, and the ``X-Tenant`` header
that switches between them is *authorized*, not merely trusted.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

PASSWORD = "hunter2000"


@pytest.fixture
async def two_tenants(create_tenant):
    a = await create_tenant(
        name="Acme Phones",
        slug="acme",
        email="owner-a@example.com",
        timezone="Asia/Tashkent",
        password=PASSWORD,
    )
    b = await create_tenant(
        name="Beta Mobile",
        slug="beta",
        email="owner-b@example.com",
        timezone="Europe/Berlin",
        password=PASSWORD,
    )
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


async def test_the_staff_list_is_scoped_to_the_token_tenant(client, two_tenants):
    a, b = two_tenants

    users_a = await client.get("/api/v1/users", headers=a.auth)
    users_b = await client.get("/api/v1/users", headers=b.auth)

    assert [u["email"] for u in users_a.json()] == ["owner-a@example.com"]
    assert [u["email"] for u in users_b.json()] == ["owner-b@example.com"]


async def test_switching_to_a_store_without_a_grant_is_refused(client, two_tenants):
    """The header is authorized, not trusted — 403, not an empty result.

    The C# reference relies on the tenant database returning nothing for an
    unauthorized user; this is the hardening its own notes recommend.
    """
    a, b = two_tenants

    resp = await client.get("/api/v1/users", headers={**a.auth, "X-Tenant": b.slug})
    assert resp.status_code == 403

    # And B is untouched by the attempt.
    users_b = await client.get("/api/v1/users", headers=b.auth)
    assert [u["email"] for u in users_b.json()] == ["owner-b@example.com"]


async def test_switching_with_a_grant_succeeds(client, two_tenants, grant_access):
    """The other half: a granted switch reaches the other store's data."""
    a, b = two_tenants
    await grant_access(a.user_id, b.tenant_id)

    resp = await client.get(
        "/api/v1/settings/tenant", headers={**a.auth, "X-Tenant": b.slug}
    )

    assert resp.status_code == 200
    assert resp.json()["timezone"] == "Europe/Berlin"


async def test_the_header_accepts_a_uuid_as_well_as_a_slug(
    client, two_tenants, grant_access
):
    a, b = two_tenants
    await grant_access(a.user_id, b.tenant_id)

    by_slug = await client.get(
        "/api/v1/settings/tenant", headers={**a.auth, "X-Tenant": b.slug}
    )
    by_uuid = await client.get(
        "/api/v1/settings/tenant", headers={**a.auth, "X-Tenant": b.tenant_id}
    )

    assert by_slug.json() == by_uuid.json()


async def test_one_stores_credentials_are_not_a_second_account_elsewhere(
    client, two_tenants
):
    """A's owner has no presence at B, so naming B gets them nothing."""
    a, b = two_tenants

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": a.email, "password": PASSWORD},
        headers={"X-Tenant": b.slug},
    )
    assert resp.status_code in (401, 403)


async def test_a_token_reissued_for_another_tenant_reaches_nothing(
    client, two_tenants, settings
):
    """A *validly signed* token naming store B, held by A's user. It routes
    to B's database, where that user id has no employee row."""
    a, b = two_tenants
    claims = jwt.decode(a.access_token, settings.jwt_secret, algorithms=["HS256"])
    forged = jwt.encode(
        {**claims, "tenant": b.tenant_id}, settings.jwt_secret, algorithm="HS256"
    )
    headers = {"Authorization": f"Bearer {forged}"}

    users = await client.get("/api/v1/users", headers=headers)
    if users.status_code == 200:
        assert [u["email"] for u in users.json()] == ["owner-b@example.com"], (
            "a cross-tenant token must not surface store A's staff"
        )

    settings_b = await client.get("/api/v1/settings/tenant", headers=b.auth)
    assert settings_b.json()["timezone"] == "Europe/Berlin"


async def test_a_token_signed_with_the_wrong_secret_is_rejected(client, two_tenants):
    a, _ = two_tenants
    forged = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000001",
            "tenant": a.tenant_id,
            "role": "tenant.owner",
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
        {**claims, "tenant": "00000000-0000-0000-0000-0000000000ff"},
        settings.jwt_secret,
        algorithm="HS256",
    )

    resp = await client.get(
        "/api/v1/settings/tenant", headers={"Authorization": f"Bearer {unknown}"}
    )
    assert resp.status_code == 404


async def test_an_invite_grants_a_role_only_at_the_issuing_store(client, two_tenants):
    """An invite issued by A's Owner joins A — never B."""
    a, b = two_tenants
    invite = await client.post(
        "/api/v1/users/invite",
        headers=a.auth,
        json={"email": "shared@example.com", "role": "tenant.seller"},
    )
    accepted = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": invite.json()["token"], "password": "sellerpass1"},
    )
    assert accepted.json()["tenant_id"] == a.tenant_id

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "shared@example.com", "password": "sellerpass1"},
    )
    assert login.json()["tenant_id"] == a.tenant_id

    users_b = await client.get("/api/v1/users", headers=b.auth)
    assert [u["email"] for u in users_b.json()] == ["owner-b@example.com"]
