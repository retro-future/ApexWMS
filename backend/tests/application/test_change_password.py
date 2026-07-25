"""Changing a password, and the exit from a provisioned temporary one."""

from uuid import uuid4

import pytest

from application.errors import InvalidCredentialsError, NotFoundError
from domain.roles import TenantRole
from tests.application.builders import make_world

OLD = "hunter2000"
NEW = "correct-horse-battery"


async def test_change_password_replaces_the_hash():
    world = make_world()
    user = world.add_user(password=OLD)

    await world.change_password().execute(user.id, OLD, NEW)

    stored = await world.users.get(user.id)
    assert stored.password_hash == world.hasher.hash(NEW)
    assert world.uow.commits == 1


async def test_changing_the_password_clears_must_change_password():
    """How a provisioned Owner (PRD §3.4) leaves the temporary password behind."""
    world = make_world()
    user = world.add_user(password=OLD, must_change_password=True, role=TenantRole.OWNER)

    await world.change_password().execute(user.id, OLD, NEW)

    assert not (await world.users.get(user.id)).must_change_password


async def test_changing_the_password_revokes_existing_sessions():
    world = make_world()
    user = world.add_user(password=OLD)
    await world.issue_refresh_for(user)

    await world.change_password().execute(user.id, OLD, NEW)

    assert all(r.is_revoked for r in world.refresh_tokens.by_id.values())


async def test_a_wrong_current_password_is_rejected():
    world = make_world()
    user = world.add_user(password=OLD, must_change_password=True)

    with pytest.raises(InvalidCredentialsError):
        await world.change_password().execute(user.id, "not-my-password", NEW)

    stored = await world.users.get(user.id)
    assert stored.password_hash == world.hasher.hash(OLD)
    assert stored.must_change_password
    assert world.uow.commits == 0


async def test_an_unknown_user_is_not_found():
    world = make_world()

    with pytest.raises(NotFoundError):
        await world.change_password().execute(uuid4(), OLD, NEW)
