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
from uuid import uuid4

from pydantic import Field

from application.common.repository import MasterDbRepository
from application.common.specification import Specification
from application.core import Command, IRequestHandler, ResultWithData
from application.errors import AlreadyMemberError, InvitationError
from application.models import AcceptInviteData
from application.ports import (
    Clock,
    MasterUnitOfWork,
    PasswordHasher,
    TenantScope,
    TokenService,
)
from application.specs import InvitationForWrite
from domain.entities import (
    Employee,
    Invitation,
    InvitationKind,
    User,
    UserAppRole,
    UserTenantAccess,
)
from infrastructure.persistence.master.models import (
    InvitationModel,
    UserAppRoleModel,
    UserModel,
    UserTenantAccessModel,
)


class AcceptInviteCommand(Command[ResultWithData[AcceptInviteData]]):
    token: str
    password: str | None = Field(default=None, min_length=8, max_length=200)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)


class AcceptInviteHandler(
    IRequestHandler[ResultWithData[AcceptInviteData], AcceptInviteCommand]
):
    def __init__(
        self,
        users: MasterDbRepository[User, UserModel],
        invitations: MasterDbRepository[Invitation, InvitationModel],
        app_roles: MasterDbRepository[UserAppRole, UserAppRoleModel],
        access: MasterDbRepository[UserTenantAccess, UserTenantAccessModel],
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

    async def handle(
        self, request: AcceptInviteCommand
    ) -> ResultWithData[AcceptInviteData]:
        invitation = await self._validate(request.token)
        now = self._clock.now()

        user = await self._users.find_one(
            Specification(UserModel).where(UserModel.email == invitation.email)
        )
        is_new = user is None
        if user is None:
            if not request.password:
                raise InvitationError("a password is required to create the account")
            user = User(
                id=uuid4(),
                email=invitation.email,
                full_name=request.full_name or invitation.email,
                password_hash=self._hasher.hash(request.password),
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
        return ResultWithData[AcceptInviteData].succeed_with_data(
            AcceptInviteData.from_entity(user, invitation)
        )

    async def _grant_app_role(self, invitation: Invitation, user: User) -> None:
        if invitation.app_role is None:
            raise InvitationError("platform invitation carries no role")
        roles_of_user = Specification(UserAppRoleModel).where(
            UserAppRoleModel.user_id == user.id
        )
        held = {a.role for a in await self._app_roles.find(roles_of_user)}
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
        has_access = Specification(UserTenantAccessModel).where(
            UserTenantAccessModel.user_id == user.id,
            UserTenantAccessModel.tenant_id == invitation.tenant_id,
        )
        if (
            not is_new
            and user.tenant_id != invitation.tenant_id
            and not await self._access.exists(has_access)
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
        parsed = self._tokens.parse_opaque(token)
        if parsed is None:
            raise InvitationError("malformed invitation token")
        invitation_id, secret = parsed
        invitation = await self._invitations.find_one(InvitationForWrite(invitation_id))
        if invitation is None or not hmac.compare_digest(
            invitation.token_hash, self._tokens.hash_opaque(secret)
        ):
            raise InvitationError("unknown invitation")
        if invitation.is_accepted:
            raise InvitationError("invitation already used")
        if invitation.is_expired(self._clock.now()):
            raise InvitationError("invitation expired")
        return invitation
