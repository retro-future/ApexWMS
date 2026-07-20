"""Owner-only user management, and the last-Owner guard."""

from uuid import uuid4

import pytest

from application.errors import LastOwnerError, NotFoundError
from domain.entities import MembershipKey
from domain.roles import Role
from tests.application.builders import make_world


async def test_list_users_returns_members_with_their_roles():
    world = make_world()
    tenant = world.add_tenant()
    owner = world.add_user(email="owner@example.com")
    seller = world.add_user(email="seller@example.com")
    world.add_member(owner, tenant, Role.OWNER)
    world.add_member(seller, tenant, Role.SELLER)

    entries = await world.list_users().execute(tenant.id)

    assert {(e.user.email, e.role) for e in entries} == {
        ("owner@example.com", Role.OWNER),
        ("seller@example.com", Role.SELLER),
    }


async def test_list_users_does_not_leak_another_tenants_members():
    world = make_world()
    mine = world.add_tenant("Acme Phones")
    theirs = world.add_tenant("Beta Mobile")
    my_owner = world.add_user(email="owner@example.com")
    their_owner = world.add_user(email="other@example.com")
    world.add_member(my_owner, mine, Role.OWNER)
    world.add_member(their_owner, theirs, Role.OWNER)

    entries = await world.list_users().execute(mine.id)

    assert [e.user.email for e in entries] == ["owner@example.com"]


async def test_change_role_updates_the_membership():
    world = make_world()
    tenant = world.add_tenant()
    owner = world.add_user(email="owner@example.com")
    seller = world.add_user(email="seller@example.com")
    world.add_member(owner, tenant, Role.OWNER)
    world.add_member(seller, tenant, Role.SELLER)

    await world.change_user_role().execute(tenant.id, seller.id, Role.MANAGER)

    assert (await world.memberships.get(MembershipKey(seller.id, tenant.id))).role is Role.MANAGER
    assert world.uow.commits == 1


async def test_demoting_the_only_owner_is_refused():
    world = make_world()
    tenant = world.add_tenant()
    owner = world.add_user(email="owner@example.com")
    world.add_member(owner, tenant, Role.OWNER)

    with pytest.raises(LastOwnerError):
        await world.change_user_role().execute(tenant.id, owner.id, Role.MANAGER)

    assert (await world.memberships.get(MembershipKey(owner.id, tenant.id))).role is Role.OWNER
    assert world.uow.commits == 0


async def test_demoting_an_owner_is_allowed_when_another_remains():
    world = make_world()
    tenant = world.add_tenant()
    first = world.add_user(email="owner@example.com")
    second = world.add_user(email="second@example.com")
    world.add_member(first, tenant, Role.OWNER)
    world.add_member(second, tenant, Role.OWNER)

    await world.change_user_role().execute(tenant.id, second.id, Role.MANAGER)

    assert (await world.memberships.get(MembershipKey(second.id, tenant.id))).role is Role.MANAGER


async def test_changing_the_role_of_a_non_member_is_not_found():
    world = make_world()
    tenant = world.add_tenant()

    with pytest.raises(NotFoundError):
        await world.change_user_role().execute(tenant.id, uuid4(), Role.MANAGER)


async def test_a_role_change_cannot_reach_into_another_tenant():
    world = make_world()
    mine = world.add_tenant("Acme Phones")
    theirs = world.add_tenant("Beta Mobile")
    outsider = world.add_user(email="outsider@example.com")
    world.add_member(outsider, theirs, Role.SELLER)

    with pytest.raises(NotFoundError):
        await world.change_user_role().execute(mine.id, outsider.id, Role.OWNER)

    assert (await world.memberships.get(MembershipKey(outsider.id, theirs.id))).role is Role.SELLER
