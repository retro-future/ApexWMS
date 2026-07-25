"""FR-1.5: the invitee accepts via the signed link and sets their password.

Two shapes, per the invitation's ``kind``:

* ``EMPLOYEE`` — creates (or reuses) the master ``User``, then an
  ``Employee`` row in the invited store keyed by that user's id.
* ``APP_USER`` — creates the master ``User`` and grants a platform role.
  No tenant database is opened at all.

An existing user keeps their password and gains a presence; only a brand
new account sets one here.

**Two databases, no distributed transaction.** The tenant write commits
before the master one, so a failure part-way leaves the invitation
unaccepted and the master side untouched — the retry is clean. The
residual window is a committed ``Employee`` whose master commit then
failed; a retry hits the unique email index on ``employees`` and fails
loudly rather than silently creating a second person.
"""

import hmac
from datetime import datetime
from uuid import UUID, uuid4

from application.dtos import AcceptInviteCommand, AcceptInviteResult
from application.errors import AlreadyMemberError, InvitationError
from application.ports import (
    Clock,
    InvitationRepository,
    MasterUnitOfWork,
    PasswordHasher,
    TenantScope,
    TokenService,
    UserAppRoleRepository,
    UserRepository,
    UserTenantAccessRepository,
)
from domain.entities import (
    Employee,
    Invitation,
    InvitationKind,
    User,
    UserAppRole,
    UserTenantAccess,
)


class AcceptInvite:
    def __init__(
        self,
        users: UserRepository,
        invitations: InvitationRepository,
        app_roles: UserAppRoleRepository,
        access: UserTenantAccessRepository,
        scope: TenantScope,
        tokens: TokenService,
        hasher: PasswordHasher,
        clock: Clock,
        uow: MasterUnitOfWork,
    ) -> None:
        self._users = users
        self._invitations = invitations
        self._app_roles = app_roles
        self._access = access
        self._scope = scope
        self._tokens = tokens
        self._hasher = hasher
        self._clock = clock
        self._uow = uow

    async def execute(self, cmd: AcceptInviteCommand) -> AcceptInviteResult:
        invitation = await self._validate(cmd.token)
        now = self._clock.now()

        user = await self._users.get_by_email(invitation.email)
        is_new = user is None
        if user is None:
            if not cmd.password:
                raise InvitationError("a password is required to create the account")
            user = User(
                id=uuid4(),
                email=invitation.email,
                full_name=cmd.full_name or invitation.email,
                password_hash=self._hasher.hash(cmd.password),
                tenant_id=invitation.tenant_id,
                is_active=True,
                created_at=now,
            )
            await self._users.add(user)

        if invitation.kind is InvitationKind.APP_USER:
            await self._grant_app_role(invitation, user)
        else:
            await self._join_store(invitation, user, is_new, now)

        invitation.accepted_at = now
        await self._invitations.update(invitation)
        await self._uow.commit()
        return AcceptInviteResult(user_id=user.id, tenant_id=invitation.tenant_id)

    async def _grant_app_role(self, invitation: Invitation, user: User) -> None:
        if invitation.app_role is None:
            raise InvitationError("platform invitation carries no role")
        held = {a.role for a in await self._app_roles.list_for_user(user.id)}
        if invitation.app_role in held:
            raise AlreadyMemberError(invitation.email)
        await self._app_roles.add(
            UserAppRole(id=uuid4(), user_id=user.id, role=invitation.app_role)
        )

    async def _join_store(
        self, invitation: Invitation, user: User, is_new: bool, now: datetime
    ) -> None:
        if invitation.tenant_id is None or invitation.tenant_role is None:
            raise InvitationError("employee invitation names no store")

        # An existing user joining a second store keeps their home tenant and
        # gains an access grant — that is what makes X-Tenant switching work.
        if (
            not is_new
            and user.tenant_id != invitation.tenant_id
            and not await self._access.exists(user.id, invitation.tenant_id)
        ):
            await self._access.add(
                UserTenantAccess(
                    id=uuid4(), user_id=user.id, tenant_id=invitation.tenant_id
                )
            )

        async with self._scope.for_tenant(invitation.tenant_id) as workspace:
            if await workspace.employees.get(user.id) is not None:
                raise AlreadyMemberError(invitation.email)
            await workspace.employees.add(
                Employee(
                    # Not a fresh id: the ledger's foreign keys depend on this
                    # matching the master user (see domain.entities.employee).
                    id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    role=invitation.tenant_role,
                    is_active=True,
                    created_at=now,
                )
            )
            await workspace.uow.commit()

    async def _validate(self, token: str) -> Invitation:
        invitation_id, secret = _parse(token)
        invitation = await self._invitations.get(invitation_id)
        if invitation is None or not hmac.compare_digest(
            invitation.token_hash, self._tokens.hash_opaque(secret)
        ):
            raise InvitationError("unknown invitation")
        if invitation.is_accepted:
            raise InvitationError("invitation already used")
        if invitation.is_expired(self._clock.now()):
            raise InvitationError("invitation expired")
        return invitation


def _parse(token: str) -> tuple[UUID, str]:
    id_part, sep, secret = token.partition(".")
    if not sep or not secret:
        raise InvitationError("malformed invitation token")
    try:
        return UUID(id_part), secret
    except ValueError:
        raise InvitationError("malformed invitation token") from None
