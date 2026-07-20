"""FR-1.2: refresh tokens rotate on use, and reuse is treated as theft."""

from datetime import timedelta
from uuid import UUID

import pytest

from application.errors import InvalidTokenError, TenantNotActiveError
from domain.entities import MembershipKey
from domain.roles import Role
from domain.tenancy import TenantStatus
from tests.application.builders import REFRESH_TTL, make_world


async def _logged_in(world, role: Role = Role.OWNER):
    tenant = world.add_tenant()
    user = world.add_user(password="hunter2000")
    world.add_member(user, tenant, role)
    token = await world.issue_refresh_for(user.id, tenant.id, role)
    return user, tenant, token


async def test_refresh_rotates_into_a_new_pair():
    world = make_world()
    _, _, token = await _logged_in(world)

    pair = await world.refresh().execute(token)

    assert pair.refresh_token != token
    assert pair.access_token


async def test_rotation_revokes_the_old_record_and_links_the_chain():
    world = make_world()
    _, _, token = await _logged_in(world)
    old_jti = token.split(".")[0]

    pair = await world.refresh().execute(token)

    old = world.refresh_tokens.by_id[UUID(old_jti)]
    assert old.is_revoked
    assert old.replaced_by == UUID(pair.refresh_token.split(".")[0])


async def test_reusing_a_rotated_token_revokes_the_whole_chain():
    """The signature response to a leaked refresh token."""
    world = make_world()
    user, tenant, token = await _logged_in(world)
    pair = await world.refresh().execute(token)

    with pytest.raises(InvalidTokenError):
        await world.refresh().execute(token)

    # Both the reused token and its live replacement are now dead.
    assert all(r.is_revoked for r in world.refresh_tokens.by_id.values())
    with pytest.raises(InvalidTokenError):
        await world.refresh().execute(pair.refresh_token)


async def test_expired_refresh_token_is_rejected():
    world = make_world()
    _, _, token = await _logged_in(world)

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
    _, _, token = await _logged_in(world)
    jti = token.split(".")[0]

    with pytest.raises(InvalidTokenError):
        await world.refresh().execute(f"{jti}.tampered-secret")


async def test_rotation_picks_up_a_role_change():
    world = make_world()
    user, tenant, token = await _logged_in(world, Role.SELLER)
    membership = await world.memberships.get(MembershipKey(user.id, tenant.id))
    membership.role = Role.MANAGER
    await world.memberships.update(membership)

    pair = await world.refresh().execute(token)

    # FakeTokenService encodes the role into the access token.
    assert pair.access_token.endswith(Role.MANAGER.value)


async def test_refresh_refuses_a_deactivated_user():
    world = make_world()
    user, _, token = await _logged_in(world)
    user.is_active = False

    with pytest.raises(InvalidTokenError):
        await world.refresh().execute(token)


async def test_refresh_refuses_a_tenant_that_left_active():
    world = make_world()
    _, tenant, token = await _logged_in(world)
    tenant.status = TenantStatus.FAILED

    with pytest.raises(TenantNotActiveError):
        await world.refresh().execute(token)
