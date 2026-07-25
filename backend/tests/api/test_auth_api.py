"""The auth surface end to end (PRD §8): login → refresh → /me, the
temporary-password flow, and the invite round trip.

No auth route requires a tenant header. Identity is master-side, so login
authenticates before any store is named and the claim is stamped from the
user's own record.
"""

import pytest

PASSWORD = "hunter2000"


async def test_login_refresh_and_me(client, create_tenant):
    tenant = await create_tenant(password=PASSWORD)

    me = await client.get("/api/v1/auth/me", headers=tenant.auth)
    assert me.status_code == 200
    assert me.json()["email"] == tenant.email
    assert me.json()["role"] == "tenant.owner"
    assert me.json()["tenant_id"] == tenant.tenant_id
    # Permissions are resolved from the role, not re-derived per request.
    assert "Permission.Users.Manage" in me.json()["permissions"]

    login = await client.post(
        "/api/v1/auth/login", json={"email": tenant.email, "password": PASSWORD}
    )
    assert login.status_code == 200
    assert login.json()["role"] == "tenant.owner"
    assert login.json()["tenant_id"] == tenant.tenant_id

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]}
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != login.json()["refresh_token"]

    still_works = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert still_works.status_code == 200


async def test_login_needs_no_tenant_header(client, create_tenant):
    """The claim comes from users.tenant_id, not from the client."""
    tenant = await create_tenant(password=PASSWORD)

    resp = await client.post(
        "/api/v1/auth/login", json={"email": tenant.email, "password": PASSWORD}
    )

    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == tenant.tenant_id


async def test_there_is_no_signup_endpoint(client):
    """PRD §3.4: stores are created by a SuperAdmin, never self-service."""
    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "tenant_name": "Acme",
            "email": "owner@example.com",
            "password": PASSWORD,
            "full_name": "Test",
            "timezone": "Asia/Tashkent",
        },
    )
    assert resp.status_code == 404


async def test_a_platform_operator_logs_in_with_no_tenant_claim(
    client, create_superadmin
):
    email, password = await create_superadmin()

    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["app_roles"] == ["app.superadmin"]
    # No store, so no tenant claim at all — not a null one.
    assert "tenant_id" not in body
    assert "role" not in body


async def test_a_provisioned_owner_must_change_the_temporary_password(
    client, create_tenant
):
    tenant = await create_tenant()  # left holding the temporary password

    login = await client.post(
        "/api/v1/auth/login", json={"email": tenant.email, "password": tenant.password}
    )
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True

    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": tenant.password, "new_password": PASSWORD},
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert changed.status_code == 204

    again = await client.post(
        "/api/v1/auth/login", json={"email": tenant.email, "password": PASSWORD}
    )
    assert again.status_code == 200
    assert again.json()["must_change_password"] is False

    stale = await client.post(
        "/api/v1/auth/login", json={"email": tenant.email, "password": tenant.password}
    )
    assert stale.status_code == 401


async def test_changing_the_password_revokes_the_old_sessions(client, create_tenant):
    tenant = await create_tenant()
    old_refresh = tenant.refresh_token

    await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": tenant.password, "new_password": PASSWORD},
        headers=tenant.auth,
    )

    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert resp.status_code == 401


async def test_a_rotated_refresh_token_cannot_be_reused(client, create_tenant):
    tenant = await create_tenant(password=PASSWORD)
    first = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tenant.refresh_token}
    )
    assert first.status_code == 200

    reused = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tenant.refresh_token}
    )
    assert reused.status_code == 401

    # Reuse revokes the chain, so the replacement dies with it.
    replacement = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first.json()["refresh_token"]}
    )
    assert replacement.status_code == 401


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer garbage"}, {"Authorization": "Basic abc"}],
)
async def test_protected_endpoints_require_a_valid_bearer_token(client, headers):
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


async def test_login_with_a_wrong_password_is_401(client, create_tenant):
    tenant = await create_tenant(password=PASSWORD)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": tenant.email, "password": "not-the-password"},
    )
    assert resp.status_code == 401


async def test_an_unknown_tenant_header_is_404(client, create_tenant):
    tenant = await create_tenant(password=PASSWORD)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": tenant.email, "password": PASSWORD},
        headers={"X-Tenant": "no-such-store"},
    )
    assert resp.status_code == 404


async def test_invite_accept_and_login_as_the_invitee(client, create_tenant):
    tenant = await create_tenant(password=PASSWORD)

    invite = await client.post(
        "/api/v1/users/invite",
        headers=tenant.auth,
        json={"email": "seller@example.com", "role": "tenant.seller"},
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["token"]

    # Accepting needs no tenant header: the invitation is master-side.
    accepted = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": token, "password": "sellerpass1", "full_name": "Nodira"},
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["tenant_id"] == tenant.tenant_id

    # Single-use.
    again = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": token, "password": "sellerpass1", "full_name": "Nodira"},
    )
    assert again.status_code == 400

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "seller@example.com", "password": "sellerpass1"},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "tenant.seller"
    assert login.json()["must_change_password"] is False


async def test_one_identity_can_work_at_two_stores(
    client, create_tenant, grant_access
):
    """FR-1.3: the same person, two stores, one login — switched by X-Tenant."""
    a = await create_tenant(
        name="Acme Phones", slug="acme", email="owner@example.com", password=PASSWORD
    )
    b = await create_tenant(
        name="Beta Mobile", slug="beta", email="beta-owner@example.com", password=PASSWORD
    )

    # Acme's owner is invited into Beta as a seller.
    invite = await client.post(
        "/api/v1/users/invite",
        headers=b.auth,
        json={"email": a.email, "role": "tenant.seller"},
    )
    assert invite.status_code == 201, invite.text
    accepted = await client.post(
        "/api/v1/auth/accept-invite", json={"token": invite.json()["token"]}
    )
    assert accepted.status_code == 201, accepted.text
    # Same identity, not a second account.
    assert accepted.json()["user_id"] == a.user_id

    # Logging in still lands at their home store.
    home = await client.post(
        "/api/v1/auth/login", json={"email": a.email, "password": PASSWORD}
    )
    assert home.json()["tenant_id"] == a.tenant_id
    assert home.json()["role"] == "tenant.owner"

    # Naming the other store switches context, with the role held *there*.
    away = await client.post(
        "/api/v1/auth/login",
        json={"email": a.email, "password": PASSWORD},
        headers={"X-Tenant": "beta"},
    )
    assert away.status_code == 200
    assert away.json()["tenant_id"] == b.tenant_id
    assert away.json()["role"] == "tenant.seller"
