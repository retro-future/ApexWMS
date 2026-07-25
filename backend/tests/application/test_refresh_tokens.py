"""FR-1.2: refresh tokens rotate on use, and reuse is treated as theft.

Claims are rebuilt on every rotation, so a role change or a revoked store
access takes effect within one access-token lifetime.
"""

from datetime import timedelta
from uuid import UUID

import pytest

from application.errors import (
    AuthenticationError,
    AuthorizationError,
    InvalidTokenError,
)
from domain.roles import TenantRole
from tests.application.builders import REFRESH_TTL, make_world


async def _logged_in(world, role: TenantRole = TenantRole.OWNER):
    user = world.add_user(password="hunter2000", role=role)
    return user, await world.issue_refresh_for(user)


async def test_refresh_rotates_into_a_new_pair():
    world = make_world()
    _, token = await _logged_in(world)

    pair = await world.refresh().execute(token)

    assert pair.refresh_token != token
    assert pair.access_token


async def test_rotation_revokes_the_old_record_and_links_the_chain():
    world = make_world()
    _, token = await _logged_in(world)
    old_jti = token.split(".")[0]

    pair = await world.refresh().execute(token)

    old = world.refresh_tokens.by_id[UUID(old_jti)]
    assert old.is_revoked
    assert old.replaced_by == UUID(pair.refresh_token.split(".")[0])


async def test_reusing_a_rotated_token_revokes_the_whole_chain():
    """The signature response to a leaked refresh token."""
    world = make_world()
    _, token = await _logged_in(world)
    pair = await world.refresh().execute(token)

    with pytest.raises(InvalidTokenError):
        await world.refresh().execute(token)

    # Both the reused token and its live replacement are now dead.
    assert all(r.is_revoked for r in world.refresh_tokens.by_id.values())
    with pytest.raises(InvalidTokenError):
        await world.refresh().execute(pair.refresh_token)


async def test_expired_refresh_token_is_rejected():
    world = make_world()
    _, token = await _logged_in(world)

    world.clock.advance(REFRESH_TTL + timedelta(seconds=1))

    with pytest.raises(InvalidTokenError):
        await world.refresh().execute(token)


@pytest.mark.parametrize(
    "token",
    ["", "no-separator", "not-a-uuid.secret", "11111111-1111-1111-1111-111111111111.wrong"],
)
async def test_malformed_or_unknown_tokens_are_rejected(token: str):
    world = make_world()
    await _logged_in(world)

    with pytest.raises(InvalidTokenError):
        await world.refresh().execute(token)


async def test_a_wrong_secret_for_a_real_jti_is_rejected():
    world = make_world()
    _, token = await _logged_in(world)
    jti = token.split(".")[0]

    with pytest.raises(InvalidTokenError):
        await world.refresh().execute(f"{jti}.tampered-secret")


async def test_rotation_picks_up_a_role_change():
    world = make_world()
    user, token = await _logged_in(world, TenantRole.SELLER)
    employee = await world.employees.get(user.id)
    employee.role = TenantRole.MANAGER
    await world.employees.update(employee)

    pair = await world.refresh().execute(token)

    # FakeTokenService encodes the claims into the access token.
    assert TenantRole.MANAGER.value in pair.access_token


async def test_rotation_can_switch_stores_when_access_exists():
    world = make_world()
    other = world.add_tenant()
    user, token = await _logged_in(world, TenantRole.OWNER)
    world.add_employee(user, other, TenantRole.SELLER)
    world.grant_access(user, other)

    pair = await world.refresh().execute(token, other.id)

    assert str(other.id) in pair.access_token
    assert TenantRole.SELLER.value in pair.access_token


async def test_rotation_cannot_switch_to_a_store_without_access():
    world = make_world()
    theirs = world.add_tenant()
    _, token = await _logged_in(world)

    with pytest.raises(AuthorizationError):
        await world.refresh().execute(token, theirs.id)


async def test_refresh_refuses_a_deactivated_identity():
    world = make_world()
    user, token = await _logged_in(world)
    user.is_active = False

    with pytest.raises(InvalidTokenError):
        await world.refresh().execute(token)


async def test_refresh_refuses_someone_no_longer_employed_here():
    world = make_world()
    user, token = await _logged_in(world)
    employee = await world.employees.get(user.id)
    employee.is_active = False

    # AuthenticationError, not the narrower InvalidTokenError: the token is
    # fine, it is the presence behind it that is gone. Either way a 401, and
    # the response must not distinguish the two.
    with pytest.raises(AuthenticationError):
        await world.refresh().execute(token)
