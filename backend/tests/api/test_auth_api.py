"""The auth surface end to end (PRD §8): signup → login → refresh → /me,
plus the invite round trip."""

import pytest


async def test_signup_login_refresh_and_me(client, sign_up):
    tenant = await sign_up()

    me = await client.get("/api/v1/auth/me", headers=tenant.auth)
    assert me.status_code == 200
    assert me.json()["email"] == tenant.email
    assert me.json()["role"] == "owner"
    assert me.json()["tenant_id"] == tenant.tenant_id

    login = await client.post(
        "/api/v1/auth/login", json={"email": tenant.email, "password": tenant.password}
    )
    assert login.status_code == 200
    assert login.json()["role"] == "owner"

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]}
    )
    assert refreshed.status_code == 200
    # The refresh token always rotates; the access token may be byte-identical
    # when minted in the same second with the same claims, which is fine.
    assert refreshed.json()["refresh_token"] != login.json()["refresh_token"]

    still_works = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert still_works.status_code == 200


async def test_a_rotated_refresh_token_cannot_be_reused(client, sign_up):
    tenant = await sign_up()
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


async def test_signup_rejects_a_duplicate_email(client, sign_up):
    await sign_up(email="owner@example.com")

    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "tenant_name": "Another Store",
            "email": "owner@example.com",
            "password": "hunter2000",
            "full_name": "Someone Else",
            "timezone": "Asia/Tashkent",
        },
    )
    assert resp.status_code == 409


async def test_signup_rejects_an_invalid_timezone(client):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "tenant_name": "Acme",
            "email": "tz@example.com",
            "password": "hunter2000",
            "full_name": "Test",
            "timezone": "Mars/Olympus_Mons",
        },
    )
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer garbage"}, {"Authorization": "Basic abc"}],
)
async def test_protected_endpoints_require_a_valid_bearer_token(client, headers):
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


async def test_login_with_a_wrong_password_is_401(client, sign_up):
    tenant = await sign_up()

    resp = await client.post(
        "/api/v1/auth/login", json={"email": tenant.email, "password": "not-the-password"}
    )
    assert resp.status_code == 401


async def test_invite_accept_and_login_as_the_invitee(client, sign_up):
    tenant = await sign_up()

    invite = await client.post(
        "/api/v1/users/invite",
        headers=tenant.auth,
        json={"email": "seller@example.com", "role": "seller"},
    )
    assert invite.status_code == 201
    token = invite.json()["token"]

    accepted = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": token, "password": "sellerpass1", "full_name": "Nodira"},
    )
    assert accepted.status_code == 200
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
    assert login.json()["role"] == "seller"


async def test_a_user_in_two_tenants_must_choose_one(client, sign_up):
    """FR-1.3: the issued token carries exactly one tenant_id."""
    first = await sign_up(name="Acme Phones", email="owner-a@example.com")
    second = await sign_up(name="Beta Mobile", email="owner-b@example.com")

    invite = await client.post(
        "/api/v1/users/invite",
        headers=second.auth,
        json={"email": first.email, "role": "manager"},
    )
    await client.post(
        "/api/v1/auth/accept-invite", json={"token": invite.json()["token"]}
    )

    ambiguous = await client.post(
        "/api/v1/auth/login", json={"email": first.email, "password": first.password}
    )
    assert ambiguous.status_code == 200
    body = ambiguous.json()
    assert "access_token" not in body
    assert {t["name"] for t in body["tenants"]} == {"Acme Phones", "Beta Mobile"}

    chosen = await client.post(
        "/api/v1/auth/login",
        json={
            "email": first.email,
            "password": first.password,
            "tenant_id": second.tenant_id,
        },
    )
    assert chosen.status_code == 200
    assert chosen.json()["tenant_id"] == second.tenant_id
    assert chosen.json()["role"] == "manager"
