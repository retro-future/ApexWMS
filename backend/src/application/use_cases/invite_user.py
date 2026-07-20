"""FR-1.5: an Owner invites a user by email with a single-use, expiring link.

M1 decision: the invite token is returned in the response for the Owner
to deliver; no email is sent.
"""

from datetime import timedelta
from uuid import UUID, uuid4

from application.dtos import InviteResult
from application.errors import AlreadyMemberError
from application.ports import (
    Clock,
    InvitationRepository,
    MasterUnitOfWork,
    MembershipRepository,
    TokenService,
    UserRepository,
)
from domain.entities import Invitation, MembershipKey
from domain.roles import Role


class InviteUser:
    def __init__(
        self,
        users: UserRepository,
        memberships: MembershipRepository,
        invitations: InvitationRepository,
        tokens: TokenService,
        clock: Clock,
        uow: MasterUnitOfWork,
        invite_ttl: timedelta,
    ) -> None:
        self._users = users
        self._memberships = memberships
        self._invitations = invitations
        self._tokens = tokens
        self._clock = clock
        self._uow = uow
        self._invite_ttl = invite_ttl

    async def execute(
        self, tenant_id: UUID, email: str, role: Role, created_by: UUID
    ) -> InviteResult:
        email = email.strip().lower()
        existing = await self._users.get_by_email(email)
        if existing is not None and await self._memberships.get(
            MembershipKey(existing.id, tenant_id)
        ):
            raise AlreadyMemberError(email)

        secret = self._tokens.new_opaque_secret()
        invitation = Invitation(
            id=uuid4(),
            tenant_id=tenant_id,
            email=email,
            role=role,
            token_hash=self._tokens.hash_opaque(secret),
            expires_at=self._clock.now() + self._invite_ttl,
            created_by=created_by,
        )
        await self._invitations.add(invitation)
        await self._uow.commit()
        return InviteResult(
            invitation_id=invitation.id,
            token=f"{invitation.id}.{secret}",
            expires_at=invitation.expires_at,
        )
