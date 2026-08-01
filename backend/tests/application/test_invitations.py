"""FR-1.5: invitations are single-use, expiring, and stored centrally.

The invitation lives in MasterDB even though it grants a role at one
store — that is what lets an invitee accept before they have any tenant
context at all.
"""

from datetime import timedelta

import pytest

from application.commands.accept_invite import AcceptInviteCommand
from application.commands.invite_user import InviteEmployeeCommand
from application.errors import AlreadyMemberError, InvitationError
from domain.entities import Invitation, InvitationKind
from domain.enums import AppRole, TenantRole
from tests.application.builders import INVITE_TTL, make_world

INVITEE = "seller@example.com"
PASSWORD = "hunter2000"


def _invite_cmd(email=INVITEE, role=TenantRole.SELLER):
    return InviteEmployeeCommand(email=email, role=role)


async def test_invite_returns_a_token_and_stores_only_its_hash():
    world = make_world()
    owner = world.add_user(email="owner@example.com", password=PASSWORD)

    result = await world.invite_user(invited_by=owner.id).handle(_invite_cmd())

    assert result.data is not None
    invitation = world.invitations.by_id[result.data.invitation_id]
    secret = result.data.token.split(".", 1)[1]
    assert invitation.token_hash == world.tokens.hash_opaque(secret)
    assert secret not in invitation.token_hash
    assert result.data.expires_at == world.clock.now() + INVITE_TTL
    assert invitation.kind is InvitationKind.EMPLOYEE
    assert invitation.tenant_id == world.tenant.id


async def test_accepting_creates_the_identity_and_the_presence():
    world = make_world()
    owner = world.add_user(email="owner@example.com", password=PASSWORD)
    invite = await world.invite_user(invited_by=owner.id).handle(_invite_cmd())
    assert invite.data is not None

    result = await world.accept_invite().handle(
        AcceptInviteCommand(token=invite.data.token, password=PASSWORD, full_name="Nodira")
    )

    assert result.data is not None
    user = await world.users.get_by_email(INVITEE)
    assert user is not None and user.id == result.data.user_id
    assert user.tenant_id == world.tenant.id
    employee = world.employees.by_id[user.id]
    # The id equality the ledger depends on.
    assert employee.id == user.id
    assert employee.role is TenantRole.SELLER
    assert user.full_name == "Nodira"
    # An invitee chooses their own password, so nothing to force a change of.
    assert not user.must_change_password


async def test_an_existing_user_joining_a_second_store_gains_access():
    """FR-1.3: one identity, several stores — the X-Tenant switching case."""
    world = make_world()
    other = world.add_tenant()
    existing = world.add_user(email=INVITEE, password=PASSWORD)
    owner = world.add_user(email="owner@example.com")
    invite = await world.invite_user(other, invited_by=owner.id).handle(
        InviteEmployeeCommand(email=INVITEE, role=TenantRole.MANAGER)
    )
    assert invite.data is not None

    result = await world.accept_invite().handle(
        AcceptInviteCommand(token=invite.data.token, password=None, full_name=None)
    )

    assert result.data is not None
    assert result.data.user_id == existing.id
    # Home store unchanged; access to the second granted.
    assert existing.tenant_id == world.tenant.id
    assert await world.access.exists(existing.id, other.id)
    assert world.scope.employees_at(other.id).by_id[existing.id].role is TenantRole.MANAGER


async def test_a_platform_invitation_touches_no_tenant_database():
    world = make_world()
    owner = world.add_user(email="owner@example.com")
    world.invitations.by_id[owner.id] = Invitation(
        id=owner.id,
        email="admin@example.com",
        kind=InvitationKind.APP_USER,
        app_role=AppRole.ADMIN,
        token_hash=world.tokens.hash_opaque("s3cret"),
        expires_at=world.clock.now() + INVITE_TTL,
        created_by=owner.id,
    )

    result = await world.accept_invite().handle(
        AcceptInviteCommand(token=f"{owner.id}.s3cret", password=PASSWORD, full_name="Admin")
    )

    assert result.data is not None
    assert result.data.tenant_id is None
    user = await world.users.get_by_email("admin@example.com")
    assert user.tenant_id is None
    roles = [a.role for a in await world.app_roles.list_for_user(user.id)]
    assert roles == [AppRole.ADMIN]
    # No presence at any store — a platform role touches no tenant database.
    assert all(user.id not in store.by_id for store in world.scope.stores.values())


async def test_an_invite_cannot_be_used_twice():
    world = make_world()
    owner = world.add_user(email="owner@example.com")
    invite = await world.invite_user(invited_by=owner.id).handle(_invite_cmd())
    assert invite.data is not None
    cmd = AcceptInviteCommand(token=invite.data.token, password=PASSWORD, full_name="Nodira")
    await world.accept_invite().handle(cmd)

    with pytest.raises(InvitationError):
        await world.accept_invite().handle(cmd)


async def test_an_expired_invite_is_rejected():
    world = make_world()
    owner = world.add_user(email="owner@example.com")
    invite = await world.invite_user(invited_by=owner.id).handle(_invite_cmd())
    assert invite.data is not None

    world.clock.advance(INVITE_TTL + timedelta(seconds=1))

    with pytest.raises(InvitationError):
        await world.accept_invite().handle(
            AcceptInviteCommand(token=invite.data.token, password=PASSWORD, full_name="Nodira")
        )


@pytest.mark.parametrize("token", ["", "no-separator", "not-a-uuid.secret"])
async def test_malformed_invite_tokens_are_rejected(token: str):
    world = make_world()

    with pytest.raises(InvitationError):
        await world.accept_invite().handle(
            AcceptInviteCommand(token=token, password=PASSWORD, full_name=None)
        )


async def test_a_tampered_invite_secret_is_rejected():
    world = make_world()
    owner = world.add_user(email="owner@example.com")
    invite = await world.invite_user(invited_by=owner.id).handle(_invite_cmd())
    assert invite.data is not None
    invitation_id = invite.data.token.split(".")[0]

    with pytest.raises(InvitationError):
        await world.accept_invite().handle(
            AcceptInviteCommand(
                token=f"{invitation_id}.tampered", password=PASSWORD, full_name=None
            )
        )


async def test_inviting_someone_who_already_works_here_is_rejected():
    world = make_world()
    owner = world.add_user(email="owner@example.com")

    with pytest.raises(AlreadyMemberError):
        await world.invite_user(invited_by=owner.id).handle(_invite_cmd(email=owner.email))


async def test_accepting_after_the_person_was_hired_anyway_is_rejected():
    """The invite was issued first, then they joined by another route."""
    world = make_world()
    owner = world.add_user(email="owner@example.com")
    invite = await world.invite_user(invited_by=owner.id).handle(_invite_cmd())
    assert invite.data is not None
    world.add_user(email=INVITEE, password=PASSWORD, role=TenantRole.MANAGER)

    with pytest.raises(AlreadyMemberError):
        await world.accept_invite().handle(
            AcceptInviteCommand(token=invite.data.token, password=PASSWORD, full_name=None)
        )


async def test_creating_an_account_without_a_password_is_rejected():
    world = make_world()
    owner = world.add_user(email="owner@example.com")
    invite = await world.invite_user(invited_by=owner.id).handle(_invite_cmd())
    assert invite.data is not None

    with pytest.raises(InvitationError):
        await world.accept_invite().handle(
            AcceptInviteCommand(token=invite.data.token, password=None, full_name="Nodira")
        )
