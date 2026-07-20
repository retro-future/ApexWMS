"""FR-1.5: invitations are single-use, expiring, and delivered as a link."""

from datetime import timedelta

import pytest

from application.dtos import AcceptInviteCommand
from application.errors import AlreadyMemberError, InvitationError
from domain.entities import MembershipKey
from domain.roles import Role
from tests.application.builders import INVITE_TTL, make_world

INVITEE = "seller@example.com"
PASSWORD = "hunter2000"


async def _owner_and_tenant(world):
    tenant = world.add_tenant()
    owner = world.add_user(email="owner@example.com", password=PASSWORD)
    world.add_member(owner, tenant, Role.OWNER)
    return owner, tenant


async def test_invite_returns_a_token_and_stores_only_its_hash():
    world = make_world()
    owner, tenant = await _owner_and_tenant(world)

    result = await world.invite_user().execute(tenant.id, INVITEE, Role.SELLER, owner.id)

    invitation = world.invitations.by_id[result.invitation_id]
    secret = result.token.split(".", 1)[1]
    assert invitation.token_hash == world.tokens.hash_opaque(secret)
    assert secret not in invitation.token_hash
    assert result.expires_at == world.clock.now() + INVITE_TTL


async def test_accepting_an_invite_creates_the_user_and_membership():
    world = make_world()
    owner, tenant = await _owner_and_tenant(world)
    invite = await world.invite_user().execute(tenant.id, INVITEE, Role.SELLER, owner.id)

    tenant_id = await world.accept_invite().execute(
        AcceptInviteCommand(token=invite.token, password=PASSWORD, full_name="Nodira")
    )

    assert tenant_id == tenant.id
    user = await world.users.get_by_email(INVITEE)
    assert user is not None and user.full_name == "Nodira"
    membership = await world.memberships.get(MembershipKey(user.id, tenant.id))
    assert membership is not None and membership.role is Role.SELLER


async def test_an_invite_cannot_be_used_twice():
    world = make_world()
    owner, tenant = await _owner_and_tenant(world)
    invite = await world.invite_user().execute(tenant.id, INVITEE, Role.SELLER, owner.id)
    cmd = AcceptInviteCommand(token=invite.token, password=PASSWORD, full_name="Nodira")
    await world.accept_invite().execute(cmd)

    with pytest.raises(InvitationError):
        await world.accept_invite().execute(cmd)


async def test_an_expired_invite_is_rejected():
    world = make_world()
    owner, tenant = await _owner_and_tenant(world)
    invite = await world.invite_user().execute(tenant.id, INVITEE, Role.SELLER, owner.id)

    world.clock.advance(INVITE_TTL + timedelta(seconds=1))

    with pytest.raises(InvitationError):
        await world.accept_invite().execute(
            AcceptInviteCommand(token=invite.token, password=PASSWORD, full_name="Nodira")
        )


@pytest.mark.parametrize("token", ["", "no-separator", "not-a-uuid.secret"])
async def test_malformed_invite_tokens_are_rejected(token: str):
    world = make_world()

    with pytest.raises(InvitationError):
        await world.accept_invite().execute(
            AcceptInviteCommand(token=token, password=PASSWORD, full_name=None)
        )


async def test_a_tampered_invite_secret_is_rejected():
    world = make_world()
    owner, tenant = await _owner_and_tenant(world)
    invite = await world.invite_user().execute(tenant.id, INVITEE, Role.SELLER, owner.id)
    invitation_id = invite.token.split(".")[0]

    with pytest.raises(InvitationError):
        await world.accept_invite().execute(
            AcceptInviteCommand(
                token=f"{invitation_id}.tampered", password=PASSWORD, full_name=None
            )
        )


async def test_an_existing_user_gains_a_second_membership():
    """FR-1.3's multi-tenant user is created here."""
    world = make_world()
    owner, tenant = await _owner_and_tenant(world)
    other_tenant = world.add_tenant("Beta Mobile")
    existing = world.add_user(email=INVITEE, password=PASSWORD)
    world.add_member(existing, other_tenant, Role.MANAGER)
    invite = await world.invite_user().execute(tenant.id, INVITEE, Role.SELLER, owner.id)

    await world.accept_invite().execute(
        AcceptInviteCommand(token=invite.token, password=None, full_name=None)
    )

    assert len(await world.memberships.list_for_user(existing.id)) == 2
    assert (await world.memberships.get(MembershipKey(existing.id, tenant.id))).role is Role.SELLER


async def test_inviting_an_existing_member_is_rejected():
    world = make_world()
    owner, tenant = await _owner_and_tenant(world)

    with pytest.raises(AlreadyMemberError):
        await world.invite_user().execute(tenant.id, owner.email, Role.MANAGER, owner.id)


async def test_creating_an_account_without_a_password_is_rejected():
    world = make_world()
    owner, tenant = await _owner_and_tenant(world)
    invite = await world.invite_user().execute(tenant.id, INVITEE, Role.SELLER, owner.id)

    with pytest.raises(InvitationError):
        await world.accept_invite().execute(
            AcceptInviteCommand(token=invite.token, password=None, full_name="Nodira")
        )
