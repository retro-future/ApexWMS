"""FR-1.5: an Owner invites someone to their store with a single-use link.

The invitation is written to MasterDB even though it grants a role in one
store, so that accepting it needs no tenant context — the invitee has none
until they have an account.

An existing platform user may be invited: they already have a login
identity, and accepting adds an ``Employee`` row at this store. What is
refused is inviting someone who already works here.

M1 decision: the invite token is returned in the response for the Owner
to deliver; no email is sent.
"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import EmailStr

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import AlreadyMemberError
from application.ports import (
    Clock,
    EmployeeRepository,
    InvitationRepository,
    MasterUnitOfWork,
    TokenService,
)
from application.types import InviteTtl, ResolvedTenantId
from domain.entities import Invitation, InvitationKind
from domain.roles import TenantRole


class InviteResultData(CamelModel):
    invitation_id: UUID
    token: str
    expires_at: datetime


class InviteEmployeeCommand(Command[ResultWithData[InviteResultData]]):
    email: EmailStr
    role: TenantRole


class InviteUserHandler(
    IRequestHandler[ResultWithData[InviteResultData], InviteEmployeeCommand]
):
    def __init__(
        self,
        employees: EmployeeRepository,
        invitations: InvitationRepository,
        tokens: TokenService,
        clock: Clock,
        uow: MasterUnitOfWork,
        invite_ttl: InviteTtl,
        tenant_id: ResolvedTenantId,
        current_user: CurrentUser,
    ) -> None:
        self._employees = employees
        self._invitations = invitations
        self._tokens = tokens
        self._clock = clock
        self._uow = uow
        self._invite_ttl = invite_ttl
        # The store resolved at the edge — the same one `employees` is bound
        # to, which is what keeps the duplicate check honest.
        self._tenant_id = tenant_id
        self._invited_by = current_user.user_id

    async def handle(
        self, request: InviteEmployeeCommand
    ) -> ResultWithData[InviteResultData]:
        email = request.email.strip().lower()
        if await self._employees.get_by_email(email) is not None:
            raise AlreadyMemberError(email)

        secret = self._tokens.new_opaque_secret()
        invitation = Invitation(
            id=uuid4(),
            email=email,
            kind=InvitationKind.EMPLOYEE,
            tenant_id=self._tenant_id,
            tenant_role=request.role,
            token_hash=self._tokens.hash_opaque(secret),
            expires_at=self._clock.now() + self._invite_ttl,
            created_by=self._invited_by,
        )
        await self._invitations.add(invitation)
        await self._uow.commit()
        return ResultWithData[InviteResultData].succeed_with_data(
            InviteResultData(
                invitation_id=invitation.id,
                token=f"{invitation.id}.{secret}",
                expires_at=invitation.expires_at,
            )
        )
