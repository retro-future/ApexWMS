"""Staff management at one store, and the last-Owner guard.

Cross-store cases are absent by construction: these use cases see one
store's ``employees`` table, so there is no other store to reach into.
That guarantee is tested where it lives — tests/api/test_tenant_isolation.py.
"""

from uuid import uuid4

import pytest

from application.commands.change_user_role import ChangeUserRoleCommand
from application.errors import LastOwnerError, NotFoundError
from application.queries.list_users import ListUsersQuery
from domain.enums import TenantRole
from tests.application.builders import make_world


async def test_list_users_returns_this_stores_staff_with_their_roles():
    world = make_world()
    world.add_user(email="owner@example.com", role=TenantRole.OWNER)
    world.add_user(email="seller@example.com", role=TenantRole.SELLER)

    result = await world.list_users().handle(ListUsersQuery())

    assert result.data is not None
    assert {(e.email, e.role) for e in result.data} == {
        ("owner@example.com", TenantRole.OWNER),
        ("seller@example.com", TenantRole.SELLER),
    }


async def test_another_stores_staff_do_not_appear():
    world = make_world()
    other = world.add_tenant()
    world.add_user(email="owner@example.com", role=TenantRole.OWNER)
    theirs = world.add_user(email="elsewhere@example.com", role=None)
    world.add_employee(theirs, other, TenantRole.OWNER)

    result = await world.list_users().handle(ListUsersQuery())

    assert result.data is not None
    assert [e.email for e in result.data] == ["owner@example.com"]


async def test_change_role_updates_the_employee_not_the_identity():
    world = make_world()
    world.add_user(email="owner@example.com", role=TenantRole.OWNER)
    seller = world.add_user(email="seller@example.com", role=TenantRole.SELLER)

    await world.change_user_role().handle(
        ChangeUserRoleCommand(role=TenantRole.MANAGER, target_user_id=seller.id)
    )

    assert (await world.employees.get(seller.id)).role is TenantRole.MANAGER
    # The master identity is untouched — a role is a per-store fact.
    assert (await world.users.get(seller.id)).tenant_id == world.tenant.id
    assert world.uow.commits == 1


async def test_demoting_the_only_owner_is_refused():
    world = make_world()
    owner = world.add_user(email="owner@example.com", role=TenantRole.OWNER)

    with pytest.raises(LastOwnerError):
        await world.change_user_role().handle(
            ChangeUserRoleCommand(role=TenantRole.MANAGER, target_user_id=owner.id)
        )

    assert (await world.employees.get(owner.id)).role is TenantRole.OWNER
    assert world.uow.commits == 0


async def test_demoting_an_owner_is_allowed_when_another_remains():
    world = make_world()
    world.add_user(email="owner@example.com", role=TenantRole.OWNER)
    second = world.add_user(email="second@example.com", role=TenantRole.OWNER)

    await world.change_user_role().handle(
        ChangeUserRoleCommand(role=TenantRole.MANAGER, target_user_id=second.id)
    )

    assert (await world.employees.get(second.id)).role is TenantRole.MANAGER


async def test_the_last_owner_guard_counts_only_this_store():
    """An Owner elsewhere is no help — each store needs its own."""
    world = make_world()
    other = world.add_tenant()
    owner = world.add_user(email="owner@example.com", role=TenantRole.OWNER)
    elsewhere = world.add_user(email="other@example.com", role=None)
    world.add_employee(elsewhere, other, TenantRole.OWNER)

    with pytest.raises(LastOwnerError):
        await world.change_user_role().handle(
            ChangeUserRoleCommand(role=TenantRole.MANAGER, target_user_id=owner.id)
        )


async def test_changing_the_role_of_someone_who_does_not_work_here_is_not_found():
    world = make_world()

    with pytest.raises(NotFoundError):
        await world.change_user_role().handle(
            ChangeUserRoleCommand(role=TenantRole.MANAGER, target_user_id=uuid4())
        )
