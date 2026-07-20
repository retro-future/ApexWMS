"""FR-1.1: signup creates a tenant, an Owner, and provisions inline."""

from dataclasses import replace

import pytest

from application.dtos import SignUpCommand
from application.errors import (
    EmailAlreadyRegisteredError,
    InvalidTimezoneError,
    ProvisioningFailedError,
)
from domain.entities import MembershipKey
from domain.roles import Role
from domain.tenancy import TenantStatus
from tests.application.builders import make_world

COMMAND = SignUpCommand(
    tenant_name="Acme Phones",
    email="Owner@Example.com",
    password="hunter2000",
    full_name="Aziz Karimov",
    timezone="Asia/Tashkent",
)


async def test_sign_up_creates_owner_tenant_and_tokens():
    world = make_world()

    result = await world.sign_up().execute(COMMAND)

    tenant = world.tenants.by_id[result.tenant_id]
    assert tenant.name == "Acme Phones"
    assert tenant.status is TenantStatus.ACTIVE
    user = await world.users.get_by_email("owner@example.com")
    assert user is not None
    membership = await world.memberships.get(MembershipKey(user.id, tenant.id))
    assert membership is not None and membership.role is Role.OWNER
    assert result.tokens.access_token and result.tokens.refresh_token


async def test_sign_up_normalizes_the_email():
    world = make_world()

    await world.sign_up().execute(COMMAND)

    assert await world.users.get_by_email("owner@example.com") is not None
    assert await world.users.get_by_email("Owner@Example.com") is None


async def test_sign_up_passes_the_timezone_to_the_provisioner():
    world = make_world()

    result = await world.sign_up().execute(replace(COMMAND, timezone="Europe/Berlin"))

    assert world.provisioner.calls == [(result.tenant_id, "Europe/Berlin")]


async def test_sign_up_rejects_a_duplicate_email():
    world = make_world()
    await world.sign_up().execute(COMMAND)

    with pytest.raises(EmailAlreadyRegisteredError):
        await world.sign_up().execute(COMMAND)


async def test_sign_up_rejects_an_unknown_timezone():
    world = make_world()

    with pytest.raises(InvalidTimezoneError):
        await world.sign_up().execute(replace(COMMAND, timezone="Mars/Olympus_Mons"))

    assert world.users.by_id == {}
    assert world.tenants.by_id == {}


async def test_failed_provisioning_leaves_the_tenant_retryable():
    """PRD §3.4: a FAILED tenant row survives so provisioning can be re-run."""
    world = make_world(provisioner_fails=True)

    with pytest.raises(ProvisioningFailedError):
        await world.sign_up().execute(COMMAND)

    tenant = next(iter(world.tenants.by_id.values()))
    assert tenant.status is TenantStatus.FAILED
    # The user and the Owner membership were committed before provisioning ran.
    user = await world.users.get_by_email("owner@example.com")
    assert user is not None
    assert await world.memberships.get(MembershipKey(user.id, tenant.id)) is not None
