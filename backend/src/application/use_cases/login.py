"""FR-1.2: email + password, authenticated against MasterDB.

Login names no tenant. Email is unique across the platform, so the
credentials alone identify the person; which store their token speaks for
is decided afterwards by ``ClaimsFactory``, from their own ``tenant_id``.

``requested_tenant_id`` is the ``X-Tenant`` header, honoured only for a
store the user actually has access to — it lets someone with accounts at
several stores land directly in one, and is ignored when absent.
"""

from uuid import UUID

from application.dtos import LoginResult
from application.errors import InvalidCredentialsError
from application.ports import MasterUnitOfWork, PasswordHasher, UserRepository
from application.use_cases.claims import ClaimsFactory
from application.use_cases.token_issuer import TokenIssuer


class Login:
    def __init__(
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        claims: ClaimsFactory,
        issuer: TokenIssuer,
        uow: MasterUnitOfWork,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._claims = claims
        self._issuer = issuer
        self._uow = uow

    async def execute(
        self, email: str, password: str, requested_tenant_id: UUID | None = None
    ) -> LoginResult:
        user = await self._users.get_by_email(email.strip().lower())
        if (
            user is None
            or user.password_hash is None
            or not self._hasher.verify(user.password_hash, password)
            or not user.is_active
        ):
            raise InvalidCredentialsError()

        claims = await self._claims.build(user, requested_tenant_id)
        tokens, _ = await self._issuer.issue(user.id, claims)
        await self._uow.commit()
        return LoginResult(
            tokens=tokens,
            must_change_password=user.must_change_password,
            tenant_id=claims.tenant_id,
            tenant_role=claims.tenant_role,
            app_roles=claims.app_roles,
        )
