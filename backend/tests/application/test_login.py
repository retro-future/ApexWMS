"""FR-1.2/FR-1.3: login, and the multi-tenant tenant-selection flow."""

import pytest

from application.errors import InvalidCredentialsError, TenantNotActiveError
from domain.roles import Role
from domain.tenancy import TenantStatus
from tests.application.builders import make_world

PASSWORD = "hunter2000"


async def test_login_issues_tokens_for_the_only_membership():
    world = make_world()
    tenant = world.add_tenant()
    user = world.add_user(password=PASSWORD)
    world.add_member(user, tenant, Role.MANAGER)

    result = await world.login().execute(user.email, PASSWORD)

    assert result.tokens is not None
    assert result.tenant_id == tenant.id
    assert result.role is Role.MANAGER
    assert result.tenant_choices is None


async def test_login_records_a_refresh_token():
    world = make_world()
    tenant = world.add_tenant()
    user = world.add_user(password=PASSWORD)
    world.add_member(user, tenant)

    await world.login().execute(user.email, PASSWORD)

    assert len(world.refresh_tokens.by_id) == 1


@pytest.mark.parametrize(
    "email, password",
    [
        ("owner@example.com", "wrong-password"),
        ("nobody@example.com", PASSWORD),
    ],
)
async def test_login_rejects_bad_credentials(email: str, password: str):
    world = make_world()
    tenant = world.add_tenant()
    user = world.add_user(password=PASSWORD)
    world.add_member(user, tenant)

    with pytest.raises(InvalidCredentialsError):
        await world.login().execute(email, password)


async def test_login_rejects_an_inactive_user():
    world = make_world()
    tenant = world.add_tenant()
    user = world.add_user(password=PASSWORD, is_active=False)
    world.add_member(user, tenant)

    with pytest.raises(InvalidCredentialsError):
        await world.login().execute(user.email, PASSWORD)


async def test_login_rejects_a_user_with_no_membership():
    world = make_world()
    user = world.add_user(password=PASSWORD)

    with pytest.raises(InvalidCredentialsError):
        await world.login().execute(user.email, PASSWORD)


async def test_multi_tenant_user_gets_choices_instead_of_tokens():
    world = make_world()
    first = world.add_tenant("Acme Phones")
    second = world.add_tenant("Beta Mobile")
    user = world.add_user(password=PASSWORD)
    world.add_member(user, first, Role.OWNER)
    world.add_member(user, second, Role.SELLER)

    result = await world.login().execute(user.email, PASSWORD)

    assert result.tokens is None
    assert {c.name for c in result.tenant_choices or []} == {"Acme Phones", "Beta Mobile"}
    assert world.refresh_tokens.by_id == {}


async def test_multi_tenant_user_selecting_a_tenant_gets_that_tenants_role():
    world = make_world()
    first = world.add_tenant("Acme Phones")
    second = world.add_tenant("Beta Mobile")
    user = world.add_user(password=PASSWORD)
    world.add_member(user, first, Role.OWNER)
    world.add_member(user, second, Role.SELLER)

    result = await world.login().execute(user.email, PASSWORD, tenant_id=second.id)

    assert result.tokens is not None
    assert result.tenant_id == second.id
    assert result.role is Role.SELLER


async def test_selecting_a_tenant_you_do_not_belong_to_is_indistinguishable_from_a_bad_password():
    world = make_world()
    mine = world.add_tenant("Acme Phones")
    theirs = world.add_tenant("Someone Else")
    user = world.add_user(password=PASSWORD)
    world.add_member(user, mine)

    with pytest.raises(InvalidCredentialsError):
        await world.login().execute(user.email, PASSWORD, tenant_id=theirs.id)


@pytest.mark.parametrize(
    "status", [TenantStatus.PENDING, TenantStatus.PROVISIONING, TenantStatus.FAILED]
)
async def test_login_refuses_a_tenant_that_is_not_active(status: TenantStatus):
    """FR-1.1: the tenant is unusable until provisioning reaches active."""
    world = make_world()
    tenant = world.add_tenant(status=status)
    user = world.add_user(password=PASSWORD)
    world.add_member(user, tenant)

    with pytest.raises(TenantNotActiveError):
        await world.login().execute(user.email, PASSWORD)
