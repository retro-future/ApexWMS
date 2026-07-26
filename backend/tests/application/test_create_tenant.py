"""PRD §3.4: a SuperAdmin creates a store; provisioning seeds its Owner."""

import pytest

from application.commands.create_superadmin import CreateSuperAdminCommand
from application.commands.create_tenant import CreateTenantCommand
from application.errors import (
    AlreadyMemberError,
    InvalidSlugError,
    InvalidTimezoneError,
    ProvisioningFailedError,
    SlugAlreadyTakenError,
)
from domain.roles import AppRole, TenantRole
from domain.tenancy import TenantStatus
from tests.application.builders import make_world

COMMAND = CreateTenantCommand(
    name="Beta Mobile",
    slug="beta",
    owner_email="Owner@Example.com",
    owner_full_name="Aziz Karimov",
    timezone="Asia/Tashkent",
)


async def test_create_tenant_provisions_it_and_returns_the_owner_credentials():
    world = make_world()

    result = await world.create_tenant().handle(COMMAND)

    assert result.data is not None
    tenant = world.tenants.by_id[result.data.tenant_id]
    assert tenant.name == "Beta Mobile"
    assert tenant.slug == "beta"
    assert tenant.status is TenantStatus.ACTIVE
    assert result.data.temporary_password


async def test_the_owner_gets_a_master_identity_scoped_to_the_new_store():
    world = make_world()

    result = await world.create_tenant().handle(COMMAND)

    assert result.data is not None
    owner = await world.users.get_by_email("owner@example.com")
    assert owner is not None
    assert owner.id == result.data.owner_user_id
    assert owner.tenant_id == result.data.tenant_id
    assert owner.must_change_password
    assert owner.password_hash == world.hasher.hash(result.data.temporary_password)


async def test_the_employee_row_shares_the_masters_user_id():
    """The equality the ledger's foreign keys will depend on from M3."""
    world = make_world()

    result = await world.create_tenant().handle(COMMAND)

    assert result.data is not None
    employee = world.scope.employees_at(result.data.tenant_id).by_id[result.data.owner_user_id]
    assert employee.id == result.data.owner_user_id
    assert employee.role is TenantRole.OWNER
    # Credentials stay master-side; the Employee carries no password.
    assert not hasattr(employee, "password_hash")


async def test_a_platform_operator_has_no_home_store():
    world = make_world()

    result = await world.create_superadmin().handle(
        CreateSuperAdminCommand(email="ops@example.com", full_name="Ops")
    )

    assert result.data is not None
    user = await world.users.get(result.data.user_id)
    assert user is not None
    assert user.tenant_id is None
    assert user.must_change_password
    assert result.data.temporary_password
    roles = [a.role for a in await world.app_roles.list_for_user(user.id)]
    assert roles == [AppRole.SUPERADMIN]


async def test_the_owner_email_is_normalized():
    world = make_world()

    await world.create_tenant().handle(COMMAND)

    assert await world.users.get_by_email("owner@example.com") is not None
    assert await world.users.get_by_email("Owner@Example.com") is None


async def test_the_timezone_and_owner_reach_the_provisioner():
    world = make_world()

    result = await world.create_tenant().handle(
        COMMAND.model_copy(update={"timezone": "Europe/Berlin"})
    )

    assert result.data is not None
    tenant_id, timezone, owner = world.provisioner.calls[0]
    assert (tenant_id, timezone) == (result.data.tenant_id, "Europe/Berlin")
    assert owner is not None and owner.user_id == result.data.owner_user_id


async def test_an_email_already_on_the_platform_cannot_own_a_new_store():
    """Identity is platform-wide now — invite them into the store instead."""
    world = make_world()
    world.add_user(email="owner@example.com")

    with pytest.raises(AlreadyMemberError):
        await world.create_tenant().handle(COMMAND)


async def test_a_duplicate_slug_is_rejected():
    world = make_world()

    with pytest.raises(SlugAlreadyTakenError):
        await world.create_tenant().handle(COMMAND.model_copy(update={"slug": "acme"}))


async def test_the_slug_is_normalized_before_the_uniqueness_check():
    world = make_world()

    with pytest.raises(SlugAlreadyTakenError):
        await world.create_tenant().handle(COMMAND.model_copy(update={"slug": "  ACME  "}))


@pytest.mark.parametrize(
    "slug", ["", "  ", "Beta Mobile", "beta_mobile", "-beta", "beta-", "beta--mobile", "b" * 64]
)
async def test_unusable_slugs_are_rejected(slug: str):
    world = make_world()

    with pytest.raises(InvalidSlugError):
        await world.create_tenant().handle(COMMAND.model_copy(update={"slug": slug}))

    assert list(world.tenants.by_id) == [world.tenant.id]


async def test_an_unknown_timezone_is_rejected_before_anything_is_written():
    world = make_world()

    with pytest.raises(InvalidTimezoneError):
        await world.create_tenant().handle(
            COMMAND.model_copy(update={"timezone": "Mars/Olympus_Mons"})
        )

    assert list(world.tenants.by_id) == [world.tenant.id]
    assert world.users.by_id == {}


async def test_failed_provisioning_leaves_the_tenant_retryable():
    """PRD §3.4: the tenant row and its Owner survive so a retry can resume."""
    world = make_world(provisioner_fails=True)

    with pytest.raises(ProvisioningFailedError):
        await world.create_tenant().handle(COMMAND)

    tenant = next(t for t in world.tenants.by_id.values() if t.slug == "beta")
    assert tenant.status is TenantStatus.FAILED
    # Committed before provisioning ran, which is what makes the retry work.
    assert world.uow.commits == 1
    assert await world.users.get_by_email("owner@example.com") is not None
