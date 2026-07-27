"""FR-1.6 / PRD §2.1: each endpoint × each role, and a 403 has no side effect."""

import pytest

ROLES = ["tenant.manager", "tenant.storekeeper", "tenant.seller"]


@pytest.fixture
async def tenant_with_roles(client, create_tenant):
    """An Owner plus one member of every other role, each with a token."""
    owner = await create_tenant(password="hunter2000")
    tokens: dict[str, dict[str, str]] = {"tenant.owner": owner.auth}
    user_ids: dict[str, str] = {}

    for role in ROLES:
        email = f"{role.split('.')[-1]}@example.com"
        invite = await client.post(
            "/api/v1/users/invite", headers=owner.auth, json={"email": email, "role": role}
        )
        assert invite.status_code == 201, invite.text
        accepted = await client.post(
            "/api/v1/auth/accept-invite",
            json={"token": invite.json()["data"]["token"], "password": "memberpass1"},
        )
        assert accepted.status_code == 201, accepted.text
        login = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "memberpass1"}
        )
        assert login.status_code == 200, login.text
        tokens[role] = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}
        user_ids[role] = accepted.json()["data"]["userId"]

    return owner, tokens, user_ids


@pytest.mark.parametrize("role", ROLES)
async def test_only_the_owner_can_list_users(client, tenant_with_roles, role):
    _, tokens, _ = tenant_with_roles

    assert (await client.get("/api/v1/users", headers=tokens["tenant.owner"])).status_code == 200
    assert (await client.get("/api/v1/users", headers=tokens[role])).status_code == 403


@pytest.mark.parametrize("role", ROLES)
async def test_only_the_owner_can_invite_and_a_403_invites_nobody(
    client, tenant_with_roles, role
):
    owner, tokens, _ = tenant_with_roles

    denied = await client.post(
        "/api/v1/users/invite",
        headers=tokens[role],
        json={"email": "sneaky@example.com", "role": "tenant.manager"},
    )
    assert denied.status_code == 403

    listed = await client.get("/api/v1/users", headers=owner.auth)
    assert "sneaky@example.com" not in [u["email"] for u in listed.json()["data"]]


@pytest.mark.parametrize("role", ROLES)
async def test_only_the_owner_can_change_roles_and_a_403_changes_nothing(
    client, tenant_with_roles, role
):
    owner, tokens, user_ids = tenant_with_roles
    target = user_ids["tenant.seller"]

    denied = await client.patch(
        f"/api/v1/users/{target}/role", headers=tokens[role], json={"role": "tenant.owner"}
    )
    assert denied.status_code == 403

    listed = await client.get("/api/v1/users", headers=owner.auth)
    roles = {u["id"]: u["role"] for u in listed.json()["data"]}
    assert roles[target] == "tenant.seller"


async def test_the_owner_can_change_a_role(client, tenant_with_roles):
    owner, _, user_ids = tenant_with_roles
    target = user_ids["tenant.seller"]

    resp = await client.patch(
        f"/api/v1/users/{target}/role", headers=owner.auth, json={"role": "tenant.manager"}
    )
    assert resp.status_code == 204

    listed = await client.get("/api/v1/users", headers=owner.auth)
    assert {u["id"]: u["role"] for u in listed.json()["data"]}[target] == "tenant.manager"


async def test_the_owner_cannot_demote_themselves_while_alone(client, tenant_with_roles):
    owner, _, _ = tenant_with_roles
    me = (await client.get("/api/v1/auth/me", headers=owner.auth)).json()["data"]

    resp = await client.patch(
        f"/api/v1/users/{me['userId']}/role", headers=owner.auth, json={"role": "tenant.manager"}
    )
    assert resp.status_code == 409


@pytest.mark.parametrize("role", ["tenant.owner", *ROLES])
async def test_any_member_can_read_tenant_settings(client, tenant_with_roles, role):
    _, tokens, _ = tenant_with_roles

    resp = await client.get("/api/v1/settings/tenant", headers=tokens[role])
    assert resp.status_code == 200
    assert resp.json()["data"]["timezone"] == "Asia/Tashkent"


@pytest.mark.parametrize("role", ROLES)
async def test_only_the_owner_can_write_tenant_settings(client, tenant_with_roles, role):
    _, tokens, _ = tenant_with_roles

    denied = await client.put(
        "/api/v1/settings/tenant", headers=tokens[role], json={"timezone": "Europe/Berlin"}
    )
    assert denied.status_code == 403

    unchanged = await client.get("/api/v1/settings/tenant", headers=tokens["tenant.owner"])
    assert unchanged.json()["data"]["timezone"] == "Asia/Tashkent"


async def test_the_owner_can_write_tenant_settings(client, tenant_with_roles):
    _, tokens, _ = tenant_with_roles

    resp = await client.put(
        "/api/v1/settings/tenant",
        headers=tokens["tenant.owner"],
        json={"timezone": "Europe/Berlin"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["timezone"] == "Europe/Berlin"


# --- M2 catalog (PRD §2.1: "Manage locations", "Manage catalog") ----------

PRODUCT = {"sku": "IP15P-256", "name": "iPhone 15 Pro", "trackingType": "serial"}


@pytest.mark.parametrize("role", ["tenant.owner", *ROLES])
@pytest.mark.parametrize("path", ["/api/v1/products", "/api/v1/locations", "/api/v1/suppliers"])
async def test_every_role_can_read_the_catalog(client, tenant_with_roles, role, path):
    """``Catalog.View``/``Location.View`` are in every tenant role's set — a
    Seller cannot sell what they cannot look up, and from M4 a Storekeeper
    receiving goods has to pick the supplier they came from."""
    _, tokens, _ = tenant_with_roles

    assert (await client.get(path, headers=tokens[role])).status_code == 200


@pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
async def test_only_a_manager_can_create_a_product_and_a_403_creates_nothing(
    client, tenant_with_roles, role
):
    owner, tokens, _ = tenant_with_roles

    denied = await client.post("/api/v1/products", headers=tokens[role], json=PRODUCT)
    assert denied.status_code == 403

    listed = await client.get("/api/v1/products", headers=owner.auth)
    assert listed.json()["data"] == []


@pytest.mark.parametrize("role", ["tenant.owner", "tenant.manager"])
async def test_an_owner_and_a_manager_can_create_a_product(client, tenant_with_roles, role):
    _, tokens, _ = tenant_with_roles

    resp = await client.post(
        "/api/v1/products", headers=tokens[role], json={**PRODUCT, "sku": f"SKU-{role}"}
    )

    assert resp.status_code == 201, resp.text


@pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
async def test_only_a_manager_can_create_a_location(client, tenant_with_roles, role):
    owner, tokens, _ = tenant_with_roles

    denied = await client.post(
        "/api/v1/locations", headers=tokens[role], json={"name": "Warehouse"}
    )
    assert denied.status_code == 403

    listed = await client.get("/api/v1/locations", headers=owner.auth)
    assert [loc["name"] for loc in listed.json()["data"]] == ["Main Store"]


@pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
async def test_only_a_manager_can_create_a_supplier(client, tenant_with_roles, role):
    _, tokens, _ = tenant_with_roles

    denied = await client.post("/api/v1/suppliers", headers=tokens[role], json={"name": "TMD"})

    assert denied.status_code == 403


@pytest.mark.parametrize("role", ["tenant.owner", "tenant.manager", "tenant.seller"])
async def test_a_seller_and_up_can_manage_customers(client, tenant_with_roles, role):
    _, tokens, _ = tenant_with_roles

    resp = await client.post(
        "/api/v1/customers", headers=tokens[role], json={"fullName": f"Customer {role}"}
    )

    assert resp.status_code == 201, resp.text


async def test_a_storekeeper_cannot_reach_the_customer_list(client, tenant_with_roles):
    """Someone receiving cartons has no reason to read who the store sells
    to — ``Permission.Customer.*`` is absent from the Storekeeper set."""
    _, tokens, _ = tenant_with_roles

    listed = await client.get("/api/v1/customers", headers=tokens["tenant.storekeeper"])
    created = await client.post(
        "/api/v1/customers", headers=tokens["tenant.storekeeper"], json={"fullName": "X"}
    )

    assert listed.status_code == 403
    assert created.status_code == 403
