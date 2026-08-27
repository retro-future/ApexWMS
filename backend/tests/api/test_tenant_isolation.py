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

    assert resp_a.json()["data"]["timezone"] == "Asia/Tashkent"
    assert resp_b.json()["data"]["timezone"] == "Europe/Berlin"


async def test_writing_one_tenants_settings_never_touches_the_other(client, two_tenants):
    a, b = two_tenants

    updated = await client.put(
        "/api/v1/settings/tenant", headers=a.auth, json={"timezone": "America/New_York"}
    )
    assert updated.status_code == 200

    assert (await client.get("/api/v1/settings/tenant", headers=a.auth)).json()["data"][
        "timezone"
    ] == "America/New_York"
    assert (await client.get("/api/v1/settings/tenant", headers=b.auth)).json()["data"][
        "timezone"
    ] == "Europe/Berlin"


async def test_the_staff_list_is_scoped_to_the_token_tenant(client, two_tenants):
    a, b = two_tenants

    users_a = await client.get("/api/v1/users", headers=a.auth)
    users_b = await client.get("/api/v1/users", headers=b.auth)

    assert [u["email"] for u in users_a.json()["data"]] == ["owner-a@example.com"]
    assert [u["email"] for u in users_b.json()["data"]] == ["owner-b@example.com"]


async def test_one_stores_catalog_is_invisible_from_the_other(client, two_tenants):
    """FR-1.4 over M2's tables. Isolation is physical, so B's product is
    not in the database A's request is connected to at all — there is no
    filter that could have been forgotten."""
    a, b = two_tenants
    await client.post(
        "/api/v1/products",
        headers=a.auth,
        json={"sku": "IP15P-256", "name": "iPhone 15 Pro", "trackingType": "serial"},
    )
    await client.post(
        "/api/v1/suppliers", headers=b.auth, json={"name": "Beta's supplier"}
    )
    await client.post(
        "/api/v1/customers", headers=b.auth, json={"fullName": "Beta's customer"}
    )

    assert (await client.get("/api/v1/products", headers=b.auth)).json()["data"] == []
    assert (await client.get("/api/v1/suppliers", headers=a.auth)).json()["data"] == []
    assert (await client.get("/api/v1/customers", headers=a.auth)).json()["data"] == []


async def test_the_same_sku_may_exist_in_both_stores(client, two_tenants):
    """The unique index is per database, so uniqueness "within the tenant"
    costs nothing across them — two shops both sell an iPhone 15 Pro."""
    a, b = two_tenants
    body = {"sku": "IP15P-256", "name": "iPhone 15 Pro", "trackingType": "serial"}

    first = await client.post("/api/v1/products", headers=a.auth, json=body)
    second = await client.post("/api/v1/products", headers=b.auth, json=body)

    assert (first.status_code, second.status_code) == (201, 201)


async def test_a_product_id_from_one_store_is_not_found_in_the_other(client, two_tenants):
    a, b = two_tenants
    created = await client.post(
        "/api/v1/products",
        headers=a.auth,
        json={"sku": "IP15P-256", "name": "iPhone 15 Pro", "trackingType": "serial"},
    )
    product_id = created.json()["data"]["id"]

    resp = await client.get(f"/api/v1/products/{product_id}", headers=b.auth)

    assert resp.status_code == 404


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
    assert [u["email"] for u in users_b.json()["data"]] == ["owner-b@example.com"]


async def test_switching_with_a_grant_succeeds(client, two_tenants, grant_access):
    """The other half: a granted switch reaches the other store's data."""
    a, b = two_tenants
    await grant_access(a.user_id, b.tenant_id)

    resp = await client.get(
        "/api/v1/settings/tenant", headers={**a.auth, "X-Tenant": b.slug}
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["timezone"] == "Europe/Berlin"


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
        assert [u["email"] for u in users.json()["data"]] == ["owner-b@example.com"], (
            "a cross-tenant token must not surface store A's staff"
        )

    settings_b = await client.get("/api/v1/settings/tenant", headers=b.auth)
    assert settings_b.json()["data"]["timezone"] == "Europe/Berlin"


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
        json={"token": invite.json()["data"]["token"], "password": "sellerpass1"},
    )
    assert accepted.json()["data"]["tenantId"] == a.tenant_id

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "shared@example.com", "password": "sellerpass1"},
    )
    assert login.json()["data"]["tenantId"] == a.tenant_id

    users_b = await client.get("/api/v1/users", headers=b.auth)
    assert [u["email"] for u in users_b.json()["data"]] == ["owner-b@example.com"]


async def test_a_stores_reports_never_see_the_other_stores_stock(client, two_tenants):
    """M8's reads are the widest surface in the system: seven endpoints that
    sweep whole tables. A report that forgot its scope would be the quietest
    possible leak, because it returns a plausible page rather than an error.
    """
    a, b = two_tenants
    created = await client.post(
        "/api/v1/products",
        headers=a.auth,
        json={"sku": "IP15P-256", "name": "iPhone 15 Pro", "trackingType": "serial"},
    )
    assert created.status_code == 201, created.text

    for path in (
        "/api/v1/reports/stock-on-hand",
        "/api/v1/reports/needs-pricing",
        "/api/v1/reports/ageing",
        "/api/v1/reports/movements",
        "/api/v1/reports/financial-ledger",
        "/api/v1/reports/price-deviations",
    ):
        seen = await client.get(path, headers=b.auth)
        assert seen.status_code == 200, seen.text
        assert seen.json()["totalItems"] == 0, path

    summary = await client.get("/api/v1/reports/sales-summary", headers=b.auth)
    assert summary.status_code == 200, summary.text
    assert summary.json()["data"]["locations"] == []


async def test_a_handset_from_one_store_cannot_be_traced_from_the_other(
    client, two_tenants
):
    a, b = two_tenants
    created = await client.post(
        "/api/v1/products",
        headers=a.auth,
        json={"sku": "IP15P-256", "name": "iPhone 15 Pro", "trackingType": "serial"},
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["data"]["id"]

    traced = await client.get(f"/api/v1/device-units/{product_id}/trace", headers=b.auth)

    assert traced.status_code == 404
