"""FR-1.2: email + password, authenticated against MasterDB.

Login names no tenant. Email is unique across the platform, so the
credentials alone identify the person; which store their token speaks for
is decided afterwards by ``ClaimsFactory``, from their own ``tenant_id``.

``RequestedTenant`` (the ``X-Tenant`` header) is honoured only for a store
the user actually has access to — it lets someone with accounts at several
stores land directly in one, and is ignored when absent.
"""

from uuid import UUID

from pydantic import EmailStr

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import RequestedTenant
from application.errors import InvalidCredentialsError
from application.ports import MasterUnitOfWork, PasswordHasher, UserRepository
from application.services.claims import ClaimsFactory
from application.services.token_issuer import TokenIssuer
from domain.enums import AppRole, TenantRole


class LoginData(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # None for a platform operator, whose token carries no tenant claim.
    tenant_id: UUID | None = None
    role: TenantRole | None = None
    app_roles: list[AppRole] = []
    # True for someone still on a provisioned temporary password.
    must_change_password: bool = False


class LoginCommand(Command[ResultWithData[LoginData]]):
    """No tenant field: email is unique platform-wide, and which store the
    token speaks for is decided server-side (PRD §3.3). An ``X-Tenant``
    header may still name one, for a person who works at several."""

    email: EmailStr
    password: str


class LoginHandler(IRequestHandler[ResultWithData[LoginData], LoginCommand]):
    def __init__(
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        claims: ClaimsFactory,
        issuer: TokenIssuer,
        uow: MasterUnitOfWork,
        requested: RequestedTenant,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._claims = claims
        self._issuer = issuer
        self._uow = uow
        self._requested_tenant_id = requested.tenant_id

    async def handle(self, request: LoginCommand) -> ResultWithData[LoginData]:
        user = await self._users.get_by_email(request.email.strip().lower())
        if (
            user is None
            or user.password_hash is None
            or not self._hasher.verify(user.password_hash, request.password)
            or not user.is_active
        ):
            raise InvalidCredentialsError()

        claims = await self._claims.build(user, self._requested_tenant_id)
        tokens, _ = await self._issuer.issue(user.id, claims)
        await self._uow.commit()
        return ResultWithData[LoginData].succeed_with_data(
            LoginData(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                must_change_password=user.must_change_password,
                tenant_id=claims.tenant_id,
                role=claims.tenant_role,
                app_roles=list(claims.app_roles),
            )
        )
