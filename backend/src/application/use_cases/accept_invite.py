"""FR-1.5: the invitee accepts via the signed link and sets their password.

An existing user (multi-tenant case) just gains a membership; a new
user is created with the supplied password. Either way the invitation
is single-use.
"""

import hmac
from uuid import UUID, uuid4

from application.dtos import AcceptInviteCommand
from application.errors import AlreadyMemberError, InvitationError
from application.ports import (
    Clock,
    InvitationRepository,
    MasterUnitOfWork,
    MembershipRepository,
    PasswordHasher,
    TokenService,
    UserRepository,
)
from domain.entities import Membership, MembershipKey, User


class AcceptInvite:
    def __init__(
        self,
        users: UserRepository,
        memberships: MembershipRepository,
        invitations: InvitationRepository,
        tokens: TokenService,
        hasher: PasswordHasher,
        clock: Clock,
        uow: MasterUnitOfWork,
    ) -> None:
        self._users = users
        self._memberships = memberships
        self._invitations = invitations
        self._tokens = tokens
        self._hasher = hasher
        self._clock = clock
        self._uow = uow

    async def execute(self, cmd: AcceptInviteCommand) -> UUID:
        """Returns the tenant_id the user joined; they log in normally after."""
        invitation_id, secret = _parse(cmd.token)
        invitation = await self._invitations.get(invitation_id)
        if invitation is None or not hmac.compare_digest(
            invitation.token_hash, self._tokens.hash_opaque(secret)
        ):
            raise InvitationError("unknown invitation")
        now = self._clock.now()
        if invitation.is_accepted:
            raise InvitationError("invitation already used")
        if invitation.is_expired(now):
            raise InvitationError("invitation expired")

        user = await self._users.get_by_email(invitation.email)
        if user is None:
            if not cmd.password:
                raise InvitationError("a password is required to create the account")
            user = User(
                id=uuid4(),
                email=invitation.email,
                full_name=cmd.full_name or invitation.email,
                password_hash=self._hasher.hash(cmd.password),
                is_active=True,
                created_at=now,
            )
            await self._users.add(user)
        else:
            key = MembershipKey(user.id, invitation.tenant_id)
            if await self._memberships.get(key) is not None:
                raise AlreadyMemberError(invitation.email)
            if user.password_hash is None and cmd.password:
                user.password_hash = self._hasher.hash(cmd.password)
                await self._users.update(user)

        await self._memberships.add(
            Membership(
                user_id=user.id, tenant_id=invitation.tenant_id, role=invitation.role
            )
        )
        invitation.accepted_at = now
        await self._invitations.update(invitation)
        await self._uow.commit()
        return invitation.tenant_id


def _parse(token: str) -> tuple[UUID, str]:
    id_part, sep, secret = token.partition(".")
    if not sep or not secret:
        raise InvitationError("malformed invitation token")
    try:
        return UUID(id_part), secret
    except ValueError:
        raise InvitationError("malformed invitation token") from None
