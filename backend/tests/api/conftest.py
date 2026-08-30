"""Fixtures shared by the API suites.

``owner`` lives here rather than in either module because both
``test_ledger_api.py`` and ``test_verify_cli.py`` need the same settled
store, and a fixture imported across test modules shadows itself.
``tenant_with_roles`` moved here for the same reason once the month-end
close needed the role matrix too.
"""

import pytest

from tests.api.ledger_helpers import PASSWORD

ROLES = ["tenant.manager", "tenant.storekeeper", "tenant.seller"]


@pytest.fixture
async def owner(create_tenant):
    """A provisioned store with its Owner logged in and past onboarding."""
    return await create_tenant(password=PASSWORD)


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

