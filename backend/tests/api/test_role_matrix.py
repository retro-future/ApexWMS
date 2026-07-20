"""FR-1.6 / PRD §2.1: each endpoint × each role, and a 403 has no side effect."""

import pytest

ROLES = ["manager", "storekeeper", "seller"]


@pytest.fixture
async def tenant_with_roles(client, sign_up):
    """An Owner plus one member of every other role, each with a token."""
    owner = await sign_up()
    tokens: dict[str, dict[str, str]] = {"owner": owner.auth}
    user_ids: dict[str, str] = {}

    for role in ROLES:
        email = f"{role}@example.com"
        invite = await client.post(
            "/api/v1/users/invite", headers=owner.auth, json={"email": email, "role": role}
        )
        assert invite.status_code == 201, invite.text
        await client.post(
            "/api/v1/auth/accept-invite",
            json={"token": invite.json()["token"], "password": "memberpass1"},
        )
        login = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "memberpass1"}
        )
        assert login.status_code == 200, login.text
        tokens[role] = {"Authorization": f"Bearer {login.json()['access_token']}"}
        user_ids[role] = login.json()["tenant_id"] and (
            await client.get("/api/v1/auth/me", headers=tokens[role])
        ).json()["user_id"]

    return owner, tokens, user_ids


@pytest.mark.parametrize("role", ROLES)
async def test_only_the_owner_can_list_users(client, tenant_with_roles, role):
    _, tokens, _ = tenant_with_roles

    assert (await client.get("/api/v1/users", headers=tokens["owner"])).status_code == 200
    assert (await client.get("/api/v1/users", headers=tokens[role])).status_code == 403


@pytest.mark.parametrize("role", ROLES)
async def test_only_the_owner_can_invite_and_a_403_invites_nobody(
    client, tenant_with_roles, role
):
    owner, tokens, _ = tenant_with_roles

    denied = await client.post(
        "/api/v1/users/invite",
        headers=tokens[role],
        json={"email": "sneaky@example.com", "role": "manager"},
    )
    assert denied.status_code == 403

    listed = await client.get("/api/v1/users", headers=owner.auth)
    assert "sneaky@example.com" not in [u["email"] for u in listed.json()]


@pytest.mark.parametrize("role", ROLES)
async def test_only_the_owner_can_change_roles_and_a_403_changes_nothing(
    client, tenant_with_roles, role
):
    owner, tokens, user_ids = tenant_with_roles
    target = user_ids["seller"]

    denied = await client.patch(
        f"/api/v1/users/{target}/role", headers=tokens[role], json={"role": "owner"}
    )
    assert denied.status_code == 403

    listed = await client.get("/api/v1/users", headers=owner.auth)
    roles = {u["id"]: u["role"] for u in listed.json()}
    assert roles[target] == "seller"


async def test_the_owner_can_change_a_role(client, tenant_with_roles):
    owner, _, user_ids = tenant_with_roles
    target = user_ids["seller"]

    resp = await client.patch(
        f"/api/v1/users/{target}/role", headers=owner.auth, json={"role": "manager"}
    )
    assert resp.status_code == 204

    listed = await client.get("/api/v1/users", headers=owner.auth)
    assert {u["id"]: u["role"] for u in listed.json()}[target] == "manager"


async def test_the_owner_cannot_demote_themselves_while_alone(client, tenant_with_roles):
    owner, _, _ = tenant_with_roles
    me = (await client.get("/api/v1/auth/me", headers=owner.auth)).json()

    resp = await client.patch(
        f"/api/v1/users/{me['user_id']}/role", headers=owner.auth, json={"role": "manager"}
    )
    assert resp.status_code == 409


@pytest.mark.parametrize("role", ["owner", *ROLES])
async def test_any_member_can_read_tenant_settings(client, tenant_with_roles, role):
    _, tokens, _ = tenant_with_roles

    resp = await client.get("/api/v1/settings/tenant", headers=tokens[role])
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "Asia/Tashkent"


@pytest.mark.parametrize("role", ROLES)
async def test_only_the_owner_can_write_tenant_settings(client, tenant_with_roles, role):
    _, tokens, _ = tenant_with_roles

    denied = await client.put(
        "/api/v1/settings/tenant", headers=tokens[role], json={"timezone": "Europe/Berlin"}
    )
    assert denied.status_code == 403

    unchanged = await client.get("/api/v1/settings/tenant", headers=tokens["owner"])
    assert unchanged.json()["timezone"] == "Asia/Tashkent"


async def test_the_owner_can_write_tenant_settings(client, tenant_with_roles):
    _, tokens, _ = tenant_with_roles

    resp = await client.put(
        "/api/v1/settings/tenant", headers=tokens["owner"], json={"timezone": "Europe/Berlin"}
    )
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "Europe/Berlin"
