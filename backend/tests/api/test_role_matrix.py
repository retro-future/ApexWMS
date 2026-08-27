"""FR-1.6 / PRD §2.1: each endpoint × each role, and a 403 has no side effect."""

from uuid import uuid4

import pytest

from tests.api.pdf_helpers import PNG_BASE64

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


@pytest.mark.parametrize("role", ROLES)
async def test_only_the_owner_can_set_the_letterhead_logo(
    client, tenant_with_roles, role
):
    """FR-8.1: the logo is a tenant setting, and those are the Owner's."""
    _, tokens, _ = tenant_with_roles

    denied = await client.put(
        "/api/v1/settings/tenant/logo",
        headers=tokens[role],
        json={"content": PNG_BASE64},
    )
    assert denied.status_code == 403

    unchanged = await client.get(
        "/api/v1/settings/tenant", headers=tokens["tenant.owner"]
    )
    assert unchanged.json()["data"]["hasLogo"] is False


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


# --- pricing (FR-2.19: setting a price is its own permission) -------------


@pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
async def test_pricing_history_is_closed_to_staff_who_cannot_see_cost(
    client, tenant_with_roles, role
):
    """§2.1 keeps a Storekeeper and a Seller out of margins; what a model
    has cost over time is the same class of figure."""
    owner, tokens, _ = tenant_with_roles
    created = await client.post(
        "/api/v1/products", headers=owner.auth, json={**PRODUCT, "defaultSalePrice": "900"}
    )
    product_id = created.json()["data"]["id"]

    denied = await client.get(
        f"/api/v1/products/{product_id}/price-history", headers=tokens[role]
    )

    assert denied.status_code == 403


@pytest.mark.parametrize("role", ["tenant.owner", "tenant.manager"])
async def test_an_owner_and_a_manager_can_read_pricing_history(
    client, tenant_with_roles, role
):
    owner, tokens, _ = tenant_with_roles
    created = await client.post(
        "/api/v1/products", headers=owner.auth, json={**PRODUCT, "defaultSalePrice": "900"}
    )
    product_id = created.json()["data"]["id"]

    resp = await client.get(
        f"/api/v1/products/{product_id}/price-history", headers=tokens[role]
    )

    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == 1


@pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
async def test_staff_cannot_price_a_handset(client, tenant_with_roles, role):
    """§2: *"a Storekeeper should not see margins or set prices"*. The
    consequence is deliberate and stated in FR-4.2b — a Seller who scans an
    unpriced used handset cannot fix it, which is why the resolution error
    names who can."""
    _, tokens, _ = tenant_with_roles

    denied = await client.patch(
        f"/api/v1/device-units/{uuid4()}/price",
        headers=tokens[role],
        json={"askingPrice": "400"},
    )

    # 403 before the handler runs, so a missing unit never becomes a 404
    # that leaks whether the IMEI exists.
    assert denied.status_code == 403


@pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
async def test_staff_cannot_bulk_reprice_or_regrade(client, tenant_with_roles, role):
    _, tokens, _ = tenant_with_roles

    bulk = await client.post(
        "/api/v1/device-units/price",
        headers=tokens[role],
        json={"prices": [{"deviceUnitId": str(uuid4()), "askingPrice": "400"}]},
    )
    condition = await client.patch(
        f"/api/v1/device-units/{uuid4()}/condition",
        headers=tokens[role],
        json={"condition": "used"},
    )

    assert (bulk.status_code, condition.status_code) == (403, 403)


@pytest.mark.parametrize("role", ["tenant.owner", *ROLES])
async def test_every_role_can_look_a_handset_up(client, tenant_with_roles, role):
    """FR-7.2: this is the "customer walks in with a phone" screen, and a
    Seller needs it. The *cost* is what they must not see — which
    ``test_device_unit_pricing.py`` covers, because it is the payload that
    narrows, not the route that closes."""
    _, tokens, _ = tenant_with_roles

    resp = await client.get(f"/api/v1/device-units/{uuid4()}", headers=tokens[role])

    assert resp.status_code == 404


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


# --- M4 purchasing & receiving (PRD §2.1, §5.3) --------------------------


@pytest.fixture
async def open_receipt(client, tenant_with_roles):
    """A draft receipt for one serialized phone, opened by the Owner."""
    owner, _, _ = tenant_with_roles

    async def post(path: str, body: dict) -> str:
        response = await client.post(f"/api/v1{path}", headers=owner.auth, json=body)
        assert response.status_code == 201, response.text
        return response.json()["data"]["id"]

    supplier_id = await post("/suppliers", {"name": "Tashkent Mobile"})
    product_id = await post(
        "/products",
        {"sku": "IP15P-ROLE", "name": "iPhone 15 Pro", "trackingType": "serial"},
    )
    locations = await client.get("/api/v1/locations", headers=owner.auth)
    receipt_id = await post(
        "/receipts",
        {
            "locationId": locations.json()["data"][0]["id"],
            "supplierId": supplier_id,
            "lines": [{"productId": product_id, "quantity": 1}],
        },
    )
    return receipt_id, supplier_id, product_id


@pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
async def test_only_a_manager_can_raise_a_purchase_order(
    client, tenant_with_roles, open_receipt, role
):
    """§2.1: "Create / send Purchase Order" is Owner and Manager only — a
    Storekeeper receives goods but does not order them.

    The body is well formed on purpose: Pydantic validates it before the
    route body runs, so a malformed one would come back 422 and prove
    nothing about the permission.
    """
    owner, tokens, _ = tenant_with_roles
    _, supplier_id, product_id = open_receipt

    denied = await client.post(
        "/api/v1/purchase-orders",
        headers=tokens[role],
        json={
            "supplierId": supplier_id,
            "lines": [{"productId": product_id, "quantity": 1, "unitCost": "700.00"}],
        },
    )
    assert denied.status_code == 403

    listed = await client.get("/api/v1/purchase-orders", headers=owner.auth)
    assert listed.json()["totalItems"] == 0


@pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
async def test_only_a_manager_can_price_an_order_line(
    client, tenant_with_roles, open_receipt, role
):
    """FR-3.1: a line may be raised unpriced; only Owner/Manager fill it in."""
    owner, tokens, _ = tenant_with_roles
    _, supplier_id, product_id = open_receipt

    raised = await client.post(
        "/api/v1/purchase-orders",
        headers=owner.auth,
        json={"supplierId": supplier_id, "lines": [{"productId": product_id, "quantity": 1}]},
    )
    assert raised.status_code == 201, raised.text
    order = raised.json()["data"]
    line_id = order["lines"][0]["id"]

    denied = await client.patch(
        f"/api/v1/purchase-orders/{order['id']}/lines/{line_id}",
        headers=tokens[role],
        json={"unitCost": "700.00"},
    )
    assert denied.status_code == 403

    priced = await client.patch(
        f"/api/v1/purchase-orders/{order['id']}/lines/{line_id}",
        headers=owner.auth,
        json={"unitCost": "700.00"},
    )
    assert priced.status_code == 200, priced.text
    assert priced.json()["data"]["lines"][0]["unitCost"] == "700.00"


@pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
async def test_a_storekeeper_cannot_even_read_purchase_orders(
    client, tenant_with_roles, role
):
    _, tokens, _ = tenant_with_roles

    assert (
        await client.get("/api/v1/purchase-orders", headers=tokens[role])
    ).status_code == 403


@pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
async def test_neither_can_print_an_order_full_of_costs(
    client, tenant_with_roles, open_receipt, role
):
    """FR-1.7: the order's page is a list of unit costs."""
    owner, tokens, _ = tenant_with_roles
    _, supplier_id, product_id = open_receipt

    raised = await client.post(
        "/api/v1/purchase-orders",
        headers=owner.auth,
        json={
            "supplierId": supplier_id,
            "lines": [{"productId": product_id, "quantity": 1, "unitCost": "700.00"}],
        },
    )
    order = raised.json()["data"]
    await client.post(
        f"/api/v1/purchase-orders/{order['id']}/confirm", headers=owner.auth, json={}
    )

    assert (
        await client.get(
            f"/api/v1/purchase-orders/{order['id']}/pdf", headers=tokens[role]
        )
    ).status_code == 403
    assert (
        await client.get(
            f"/api/v1/purchase-orders/{order['id']}/pdf", headers=owner.auth
        )
    ).status_code == 200


@pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
async def test_neither_can_print_a_supplier_return(client, tenant_with_roles, role):
    _, tokens, _ = tenant_with_roles

    assert (
        await client.get(
            f"/api/v1/supplier-returns/{uuid4()}/pdf", headers=tokens[role]
        )
    ).status_code == 403


async def test_a_seller_cannot_receive_goods(client, tenant_with_roles, open_receipt):
    """A Seller sells but cannot receive — §2.1's matrix is not a rank."""
    _, tokens, _ = tenant_with_roles
    receipt_id, _, _ = open_receipt

    assert (
        await client.get("/api/v1/receipts", headers=tokens["tenant.seller"])
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/receipts/{receipt_id}/scan",
            headers=tokens["tenant.seller"],
            json={"imei": "490154203237518"},
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/receipts/{receipt_id}/confirm",
            headers=tokens["tenant.seller"],
            json={},
        )
    ).status_code == 403


async def test_a_storekeeper_scans_but_may_not_price(
    client, tenant_with_roles, open_receipt
):
    """FR-3.4b: a Storekeeper scans IMEIs and states condition. Cost and
    asking price need the pricing permission, and a 403 scans nothing."""
    owner, tokens, _ = tenant_with_roles
    receipt_id, _, _ = open_receipt
    storekeeper = tokens["tenant.storekeeper"]

    priced_scan = await client.post(
        f"/api/v1/receipts/{receipt_id}/scan",
        headers=storekeeper,
        json={"imei": "490154203237518", "acquisitionCost": "700.00"},
    )
    assert priced_scan.status_code == 403

    seen = await client.get(f"/api/v1/receipts/{receipt_id}", headers=owner.auth)
    assert seen.json()["data"]["lines"][0]["scannedCount"] == 0

    plain_scan = await client.post(
        f"/api/v1/receipts/{receipt_id}/scan",
        headers=storekeeper,
        json={"imei": "490154203237518", "condition": "used"},
    )
    assert plain_scan.status_code == 200, plain_scan.text

    repriced = await client.patch(
        f"/api/v1/receipts/{receipt_id}/scan/490154203237518",
        headers=storekeeper,
        json={"askingPrice": "520.00"},
    )
    assert repriced.status_code == 403


async def test_a_storekeeper_reads_the_asking_price_and_never_the_cost(
    client, tenant_with_roles, open_receipt
):
    """FR-1.7: response shaping, not UI hiding. Hiding the cost is what
    makes a margin uncomputable; the sale price is what the shop needs."""
    owner, tokens, _ = tenant_with_roles
    receipt_id, _, _ = open_receipt

    await client.post(
        f"/api/v1/receipts/{receipt_id}/scan",
        headers=owner.auth,
        json={
            "imei": "490154203237518",
            "condition": "used",
            "acquisitionCost": "410.00",
            "askingPrice": "520.00",
            "cashPaid": "5000000",
            "cashPaidCurrency": "UZS",
        },
    )

    as_storekeeper = await client.get(
        f"/api/v1/receipts/{receipt_id}", headers=tokens["tenant.storekeeper"]
    )
    assert as_storekeeper.status_code == 200, as_storekeeper.text
    unit = as_storekeeper.json()["data"]["lines"][0]["units"][0]
    assert unit["askingPrice"] == "520.00"
    assert unit["acquisitionCost"] is None
    assert unit["acquisitionCostMinor"] is None
    assert unit["cashPaid"] is None
    assert as_storekeeper.json()["data"]["subtotals"] == []

    as_owner = await client.get(f"/api/v1/receipts/{receipt_id}", headers=owner.auth)
    owned_unit = as_owner.json()["data"]["lines"][0]["units"][0]
    assert owned_unit["acquisitionCost"] == "410.00"
    assert "5 000 000" in owned_unit["cashPaid"]


@pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
async def test_only_a_manager_can_cancel_a_confirmed_document(
    client, tenant_with_roles, open_receipt, role
):
    owner, tokens, _ = tenant_with_roles
    receipt_id, _, _ = open_receipt
    await client.post(
        f"/api/v1/receipts/{receipt_id}/scan",
        headers=owner.auth,
        json={"imei": "490154203237518", "acquisitionCost": "700.00"},
    )
    await client.post(
        f"/api/v1/receipts/{receipt_id}/confirm", headers=owner.auth, json={}
    )

    denied = await client.post(
        f"/api/v1/receipts/{receipt_id}/cancel", headers=tokens[role], json={}
    )
    assert denied.status_code == 403

    still = await client.get(f"/api/v1/receipts/{receipt_id}", headers=owner.auth)
    assert still.json()["data"]["status"] == "confirmed"


REPORTS = [
    "/api/v1/reports/stock-on-hand",
    "/api/v1/reports/needs-pricing",
    "/api/v1/reports/ageing",
    "/api/v1/reports/movements",
    "/api/v1/reports/sales-summary",
    "/api/v1/reports/financial-ledger",
]


@pytest.mark.parametrize("path", REPORTS)
async def test_reporting_is_owner_and_manager_only(client, tenant_with_roles, path):
    """§2.1: operational reporting and the financial ledger are both the
    Owner's and the Manager's, and neither is anybody else's."""
    _, tokens, _ = tenant_with_roles

    for role in ("tenant.owner", "tenant.manager"):
        allowed = await client.get(path, headers=tokens[role])
        assert allowed.status_code == 200, f"{path} for {role}: {allowed.text}"

    for role in ("tenant.storekeeper", "tenant.seller"):
        refused = await client.get(path, headers=tokens[role])
        assert refused.status_code == 403, f"{path} for {role}"
