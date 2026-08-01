"""FR-1.2/FR-1.3: login against MasterDB, tenant stamped server-side.

Login names no tenant. The claim comes from the user's own record, so the
client cannot choose which store its token speaks for — only request one
it already has access to.
"""

import pytest

from application.commands.create_superadmin import CreateSuperAdminCommand
from application.commands.login import LoginCommand
from application.errors import (
    AuthorizationError,
    InvalidCredentialsError,
    TenantNotActiveError,
)
from domain.enums import AppRole, TenantRole, TenantStatus
from tests.application.builders import make_world

PASSWORD = "hunter2000"


async def test_login_stamps_the_tenant_from_the_users_own_record():
    world = make_world()
    user = world.add_user(password=PASSWORD, role=TenantRole.MANAGER)

    result = await world.login().handle(LoginCommand(email=user.email, password=PASSWORD))

    assert result.data is not None
    assert result.data.tenant_id == world.tenant.id
    assert result.data.role is TenantRole.MANAGER
    assert not result.data.must_change_password


async def test_the_role_comes_from_the_store_not_the_login_identity():
    """Two stores may grade the same person differently — the Employee row
    at the store being entered is what decides."""
    world = make_world()
    other = world.add_tenant()
    user = world.add_user(password=PASSWORD, role=TenantRole.SELLER)
    world.add_employee(user, other, TenantRole.MANAGER)
    world.grant_access(user, other)

    home = await world.login().handle(LoginCommand(email=user.email, password=PASSWORD))
    away = await world.login(other.id).handle(LoginCommand(email=user.email, password=PASSWORD))

    assert home.data is not None and home.data.role is TenantRole.SELLER
    assert away.data is not None and away.data.role is TenantRole.MANAGER


async def test_login_records_a_refresh_token():
    world = make_world()
    user = world.add_user(password=PASSWORD)

    await world.login().handle(LoginCommand(email=user.email, password=PASSWORD))

    assert len(world.refresh_tokens.by_id) == 1


async def test_a_platform_operator_gets_no_tenant_claim():
    world = make_world()
    result = await world.create_superadmin().handle(
        CreateSuperAdminCommand(email="ops@example.com", full_name="Ops")
    )
    assert result.data is not None
    user = await world.users.get(result.data.user_id)
    assert user is not None
    user.password_hash = world.hasher.hash(PASSWORD)

    login_result = await world.login().handle(LoginCommand(email=user.email, password=PASSWORD))

    assert login_result.data is not None
    assert login_result.data.tenant_id is None
    assert login_result.data.role is None
    assert login_result.data.app_roles == [AppRole.SUPERADMIN]


async def test_requesting_a_store_the_user_may_not_enter_is_refused():
    world = make_world()
    theirs = world.add_tenant()
    user = world.add_user(password=PASSWORD)

    with pytest.raises(AuthorizationError):
        await world.login(theirs.id).handle(LoginCommand(email=user.email, password=PASSWORD))


async def test_a_granted_store_can_be_requested_at_login():
    world = make_world()
    other = world.add_tenant()
    user = world.add_user(password=PASSWORD)
    world.add_employee(user, other, TenantRole.SELLER)
    world.grant_access(user, other)

    result = await world.login(other.id).handle(LoginCommand(email=user.email, password=PASSWORD))

    assert result.data is not None
    assert result.data.tenant_id == other.id


async def test_an_identity_with_no_presence_at_the_store_cannot_log_in():
    """The master account is fine but there is no Employee row — treated as
    bad credentials rather than leaking that the account exists."""
    world = make_world()
    user = world.add_user(password=PASSWORD, role=None, tenant=world.tenant)

    with pytest.raises(InvalidCredentialsError):
        await world.login().handle(LoginCommand(email=user.email, password=PASSWORD))


async def test_a_deactivated_employee_cannot_log_in():
    world = make_world()
    user = world.add_user(password=PASSWORD)
    world.employees.by_id[user.id].is_active = False

    with pytest.raises(InvalidCredentialsError):
        await world.login().handle(LoginCommand(email=user.email, password=PASSWORD))


async def test_login_reports_a_temporary_password_that_must_be_changed():
    world = make_world()
    user = world.add_user(password=PASSWORD, must_change_password=True)

    result = await world.login().handle(LoginCommand(email=user.email, password=PASSWORD))

    assert result.data is not None
    assert result.data.must_change_password
    # Tokens are still issued: the change-password endpoint needs them.
    assert result.data.access_token


async def test_login_normalizes_the_email():
    world = make_world()
    world.add_user(email="owner@example.com", password=PASSWORD)

    result = await world.login().handle(
        LoginCommand(email="  Owner@Example.COM ", password=PASSWORD)
    )

    assert result.data is not None
    assert result.data.access_token


@pytest.mark.parametrize(
    "email, password",
    [("owner@example.com", "wrong-password"), ("nobody@example.com", PASSWORD)],
)
async def test_login_rejects_bad_credentials(email: str, password: str):
    world = make_world()
    world.add_user(password=PASSWORD)

    with pytest.raises(InvalidCredentialsError):
        await world.login().handle(LoginCommand(email=email, password=password))


async def test_login_rejects_a_deactivated_identity():
    world = make_world()
    user = world.add_user(password=PASSWORD, is_active=False)

    with pytest.raises(InvalidCredentialsError):
        await world.login().handle(LoginCommand(email=user.email, password=PASSWORD))


async def test_login_rejects_a_user_who_has_not_set_a_password():
    world = make_world()
    user = world.add_user(password="")

    with pytest.raises(InvalidCredentialsError):
        await world.login().handle(LoginCommand(email=user.email, password=PASSWORD))


async def test_login_refuses_a_store_that_is_not_active():
    """A suspended store is unreachable through the claims path too."""
    world = make_world()
    user = world.add_user(password=PASSWORD)
    world.tenant.status = TenantStatus.SUSPENDED

    with pytest.raises(TenantNotActiveError):
        await world.login().handle(LoginCommand(email=user.email, password=PASSWORD))
