"""FR-1.1: an anonymous visitor creates a tenant and becomes its Owner."""

from uuid import uuid4

from application.dtos import SignUpCommand, SignUpResult
from application.errors import EmailAlreadyRegisteredError
from application.ports import (
    Clock,
    MasterUnitOfWork,
    MembershipRepository,
    PasswordHasher,
    TenantProvisioner,
    TenantRepository,
    UserRepository,
)
from application.timezones import validate_timezone
from application.use_cases.token_issuer import TokenIssuer
from domain.entities import Membership, Tenant, User
from domain.roles import Role
from domain.tenancy import TenantStatus


class SignUp:
    def __init__(
        self,
        users: UserRepository,
        tenants: TenantRepository,
        memberships: MembershipRepository,
        hasher: PasswordHasher,
        provisioner: TenantProvisioner,
        issuer: TokenIssuer,
        clock: Clock,
        uow: MasterUnitOfWork,
    ) -> None:
        self._users = users
        self._tenants = tenants
        self._memberships = memberships
        self._hasher = hasher
        self._provisioner = provisioner
        self._issuer = issuer
        self._clock = clock
        self._uow = uow

    async def execute(self, cmd: SignUpCommand) -> SignUpResult:
        validate_timezone(cmd.timezone)
        email = cmd.email.strip().lower()
        if await self._users.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError(email)

        now = self._clock.now()
        user = User(
            id=uuid4(),
            email=email,
            full_name=cmd.full_name,
            password_hash=self._hasher.hash(cmd.password),
            is_active=True,
            created_at=now,
        )
        tenant = Tenant(
            id=uuid4(), name=cmd.tenant_name, status=TenantStatus.PENDING, created_at=now
        )
        await self._users.add(user)
        await self._tenants.add(tenant)
        await self._memberships.add(
            Membership(user_id=user.id, tenant_id=tenant.id, role=Role.OWNER)
        )
        # Commit before provisioning: the pending tenant row must survive a
        # provisioning crash so the operation is retryable (PRD §3.4).
        await self._uow.commit()

        await self._provisioner.provision(tenant.id, cmd.timezone)

        tokens, _ = await self._issuer.issue(user.id, tenant.id, Role.OWNER)
        await self._uow.commit()
        return SignUpResult(tenant_id=tenant.id, tokens=tokens)
