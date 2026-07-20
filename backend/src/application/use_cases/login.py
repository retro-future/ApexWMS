"""FR-1.2/FR-1.3: email+password login; multi-tenant users pick a tenant.

The issued token carries exactly one tenant_id. A user with several
memberships and no tenant selected gets the tenant list back instead
of tokens.
"""

from uuid import UUID

from application.dtos import LoginResult, TenantChoice
from application.errors import InvalidCredentialsError, TenantNotActiveError
from application.ports import (
    MasterUnitOfWork,
    MembershipRepository,
    PasswordHasher,
    TenantRepository,
    UserRepository,
)
from application.use_cases.token_issuer import TokenIssuer
from domain.tenancy import TenantStatus


class Login:
    def __init__(
        self,
        users: UserRepository,
        tenants: TenantRepository,
        memberships: MembershipRepository,
        hasher: PasswordHasher,
        issuer: TokenIssuer,
        uow: MasterUnitOfWork,
    ) -> None:
        self._users = users
        self._tenants = tenants
        self._memberships = memberships
        self._hasher = hasher
        self._issuer = issuer
        self._uow = uow

    async def execute(
        self, email: str, password: str, tenant_id: UUID | None = None
    ) -> LoginResult:
        user = await self._users.get_by_email(email.strip().lower())
        if (
            user is None
            or user.password_hash is None
            or not self._hasher.verify(user.password_hash, password)
            or not user.is_active
        ):
            raise InvalidCredentialsError()

        memberships = await self._memberships.list_for_user(user.id)
        if not memberships:
            raise InvalidCredentialsError()

        if tenant_id is None:
            if len(memberships) > 1:
                choices = []
                for m in memberships:
                    tenant = await self._tenants.get(m.tenant_id)
                    if tenant is not None:
                        choices.append(TenantChoice(tenant.id, tenant.name))
                return LoginResult(tokens=None, tenant_id=None, role=None, tenant_choices=choices)
            tenant_id = memberships[0].tenant_id

        membership = next((m for m in memberships if m.tenant_id == tenant_id), None)
        if membership is None:
            # Selecting a tenant one doesn't belong to reveals nothing more
            # than a wrong password would.
            raise InvalidCredentialsError()

        tenant = await self._tenants.get(tenant_id)
        if tenant is None or tenant.status is not TenantStatus.ACTIVE:
            raise TenantNotActiveError()

        tokens, _ = await self._issuer.issue(user.id, tenant_id, membership.role)
        await self._uow.commit()
        return LoginResult(
            tokens=tokens, tenant_id=tenant_id, role=membership.role, tenant_choices=None
        )
