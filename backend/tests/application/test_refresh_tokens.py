"""FR-1.2: refresh tokens rotate on use, and reuse is treated as theft.

Claims are rebuilt on every rotation, so a role change or a revoked store
access takes effect within one access-token lifetime.
"""

from datetime import timedelta
from uuid import UUID

import pytest

from application.commands.refresh_tokens import RefreshTokensCommand
from application.errors import (
    AuthenticationError,
    AuthorizationError,
    InvalidTokenError,
)
from domain.enums import TenantRole
from tests.application.builders import REFRESH_TTL, make_world


async def _logged_in(world, role: TenantRole = TenantRole.OWNER):
    user = world.add_user(password="hunter2000", role=role)
    return user, await world.issue_refresh_for(user)


async def test_refresh_rotates_into_a_new_pair():
    world = make_world()
    _, token = await _logged_in(world)

    result = await world.refresh().handle(RefreshTokensCommand(refresh_token=token))

    assert result.data is not None
    assert result.data.refresh_token != token
    assert result.data.access_token


async def test_rotation_revokes_the_old_record_and_links_the_chain():
    world = make_world()
    _, token = await _logged_in(world)
    old_jti = token.split(".")[0]

    result = await world.refresh().handle(RefreshTokensCommand(refresh_token=token))

    assert result.data is not None
    old = world.refresh_tokens.by_id[UUID(old_jti)]
    assert old.is_revoked
    assert old.replaced_by == UUID(result.data.refresh_token.split(".")[0])


async def test_reusing_a_rotated_token_revokes_the_whole_chain():
    """The signature response to a leaked refresh token."""
    world = make_world()
    _, token = await _logged_in(world)
    result = await world.refresh().handle(RefreshTokensCommand(refresh_token=token))
    assert result.data is not None

    with pytest.raises(InvalidTokenError):
        await world.refresh().handle(RefreshTokensCommand(refresh_token=token))

    # Both the reused token and its live replacement are now dead.
    assert all(r.is_revoked for r in world.refresh_tokens.by_id.values())
    with pytest.raises(InvalidTokenError):
        await world.refresh().handle(RefreshTokensCommand(refresh_token=result.data.refresh_token))


async def test_expired_refresh_token_is_rejected():
    world = make_world()
    _, token = await _logged_in(world)

    world.clock.advance(REFRESH_TTL + timedelta(seconds=1))

    with pytest.raises(InvalidTokenError):
        await world.refresh().handle(RefreshTokensCommand(refresh_token=token))


@pytest.mark.parametrize(
    "token",
    ["", "no-separator", "not-a-uuid.secret", "11111111-1111-1111-1111-111111111111.wrong"],
)
async def test_malformed_or_unknown_tokens_are_rejected(token: str):
    world = make_world()
    await _logged_in(world)

    with pytest.raises(InvalidTokenError):
        await world.refresh().handle(RefreshTokensCommand(refresh_token=token))


async def test_a_wrong_secret_for_a_real_jti_is_rejected():
    world = make_world()
    _, token = await _logged_in(world)
    jti = token.split(".")[0]

    with pytest.raises(InvalidTokenError):
        await world.refresh().handle(RefreshTokensCommand(refresh_token=f"{jti}.tampered-secret"))


async def test_rotation_picks_up_a_role_change():
    world = make_world()
    user, token = await _logged_in(world, TenantRole.SELLER)
    employee = await world.employees.get(user.id)
    employee.role = TenantRole.MANAGER
    await world.employees.update(employee)

    result = await world.refresh().handle(RefreshTokensCommand(refresh_token=token))

    # FakeTokenService encodes the claims into the access token.
    assert result.data is not None
    assert TenantRole.MANAGER.value in result.data.access_token


async def test_rotation_can_switch_stores_when_access_exists():
    world = make_world()
    other = world.add_tenant()
    user, token = await _logged_in(world, TenantRole.OWNER)
    world.add_employee(user, other, TenantRole.SELLER)
    world.grant_access(user, other)

    result = await world.refresh(other.id).handle(RefreshTokensCommand(refresh_token=token))

    assert result.data is not None
    assert str(other.id) in result.data.access_token
    assert TenantRole.SELLER.value in result.data.access_token


async def test_rotation_cannot_switch_to_a_store_without_access():
    world = make_world()
    theirs = world.add_tenant()
    _, token = await _logged_in(world)

    with pytest.raises(AuthorizationError):
        await world.refresh(theirs.id).handle(RefreshTokensCommand(refresh_token=token))


async def test_refresh_refuses_a_deactivated_identity():
    world = make_world()
    user, token = await _logged_in(world)
    user.is_active = False

    with pytest.raises(InvalidTokenError):
        await world.refresh().handle(RefreshTokensCommand(refresh_token=token))


async def test_refresh_refuses_someone_no_longer_employed_here():
    world = make_world()
    user, token = await _logged_in(world)
    employee = await world.employees.get(user.id)
    employee.is_active = False

    # AuthenticationError, not the narrower InvalidTokenError: the token is
    # fine, it is the presence behind it that is gone. Either way a 401, and
    # the response must not distinguish the two.
    with pytest.raises(AuthenticationError):
        await world.refresh().handle(RefreshTokensCommand(refresh_token=token))
