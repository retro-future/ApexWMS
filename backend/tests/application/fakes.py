"""In-memory fakes for the application ports (PRD §9 Testing:
use cases are tested with no database at all).

The split mirrors the real one: ``FakeUserRepository`` and friends stand
for MasterDB, ``FakeEmployeeRepository`` for one store's database, and
``FakeTenantScope`` for reaching a store the edge did not resolve.
"""

import hashlib
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from application.dtos import OwnerSeed, RefreshTokenParts
from application.errors import ProvisioningFailedError, TenantNotActiveError
from domain.entities import (
    Employee,
    Invitation,
    RefreshTokenRecord,
    Tenant,
    User,
    UserAppRole,
    UserTenantAccess,
)
from domain.roles import AppRole, TenantRole
from domain.tenancy import TenantStatus


class FakeClock:
    def __init__(self, start: datetime | None = None) -> None:
        self.current = start or datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


class FakeHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == f"hashed:{password}"


class FakeTokenService:
    def issue_access(
        self,
        user_id: UUID,
        tenant_id: UUID | None,
        tenant_role: TenantRole | None,
        app_roles: Sequence[AppRole] = (),
    ) -> str:
        # Encodes the claims so tests can assert on what a token says.
        tenant = tenant_id or "none"
        role = tenant_role.value if tenant_role else "none"
        apps = "+".join(r.value for r in app_roles) or "none"
        return f"access:{user_id}:{tenant}:{role}:{apps}"

    def issue_refresh(self) -> RefreshTokenParts:
        secret = uuid4().hex
        return RefreshTokenParts(jti=uuid4(), secret=secret, token_hash=self.hash_opaque(secret))

    def new_opaque_secret(self) -> str:
        return uuid4().hex

    def hash_opaque(self, secret: str) -> str:
        return hashlib.sha256(secret.encode()).hexdigest()


# --- MasterDB -------------------------------------------------------------


class FakeUserRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, User] = {}

    async def get(self, user_id: UUID) -> User | None:
        return self.by_id.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.by_id.values() if u.email == email), None)

    async def add(self, user: User) -> None:
        self.by_id[user.id] = user

    async def update(self, user: User) -> None:
        self.by_id[user.id] = user


class FakeUserAppRoleRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, UserAppRole] = {}

    async def get(self, key: UUID) -> UserAppRole | None:
        return self.by_id.get(key)

    async def list_for_user(self, user_id: UUID) -> list[UserAppRole]:
        return [a for a in self.by_id.values() if a.user_id == user_id]

    async def add(self, assignment: UserAppRole) -> None:
        self.by_id[assignment.id] = assignment

    async def update(self, assignment: UserAppRole) -> None:
        self.by_id[assignment.id] = assignment


class FakeUserTenantAccessRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, UserTenantAccess] = {}

    async def get(self, key: UUID) -> UserTenantAccess | None:
        return self.by_id.get(key)

    async def list_for_user(self, user_id: UUID) -> list[UserTenantAccess]:
        return [g for g in self.by_id.values() if g.user_id == user_id]

    async def exists(self, user_id: UUID, tenant_id: UUID) -> bool:
        return any(
            g.user_id == user_id and g.tenant_id == tenant_id
            for g in self.by_id.values()
        )

    async def add(self, grant: UserTenantAccess) -> None:
        self.by_id[grant.id] = grant

    async def update(self, grant: UserTenantAccess) -> None:
        self.by_id[grant.id] = grant


class FakeTenantRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Tenant] = {}

    async def get(self, tenant_id: UUID) -> Tenant | None:
        return self.by_id.get(tenant_id)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        return next((t for t in self.by_id.values() if t.slug == slug), None)

    async def list_all(self) -> list[Tenant]:
        return sorted(self.by_id.values(), key=lambda t: t.created_at)

    async def add(self, tenant: Tenant) -> None:
        self.by_id[tenant.id] = tenant

    async def update(self, tenant: Tenant) -> None:
        self.by_id[tenant.id] = tenant


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, RefreshTokenRecord] = {}

    async def get(self, jti: UUID) -> RefreshTokenRecord | None:
        return self.by_id.get(jti)

    async def add(self, record: RefreshTokenRecord) -> None:
        self.by_id[record.id] = record

    async def update(self, record: RefreshTokenRecord) -> None:
        self.by_id[record.id] = record

    async def revoke_all_for_user(self, user_id: UUID, now: datetime) -> None:
        for record in self.by_id.values():
            if record.user_id == user_id and record.revoked_at is None:
                record.revoked_at = now


class FakeInvitationRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Invitation] = {}

    async def get(self, invitation_id: UUID) -> Invitation | None:
        return self.by_id.get(invitation_id)

    async def add(self, invitation: Invitation) -> None:
        self.by_id[invitation.id] = invitation

    async def update(self, invitation: Invitation) -> None:
        self.by_id[invitation.id] = invitation


# --- one tenant's database ------------------------------------------------


class FakeEmployeeRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Employee] = {}

    async def get(self, user_id: UUID) -> Employee | None:
        return self.by_id.get(user_id)

    async def get_by_email(self, email: str) -> Employee | None:
        return next((e for e in self.by_id.values() if e.email == email), None)

    async def list_all(self) -> list[Employee]:
        return sorted(self.by_id.values(), key=lambda e: e.created_at)

    async def count_owners(self) -> int:
        return sum(
            1 for e in self.by_id.values() if e.role is TenantRole.OWNER and e.is_active
        )

    async def add(self, employee: Employee) -> None:
        self.by_id[employee.id] = employee

    async def update(self, employee: Employee) -> None:
        self.by_id[employee.id] = employee


class FakeTenantSettingsRepository:
    def __init__(self, timezone: str = "Asia/Tashkent") -> None:
        self.timezone = timezone

    async def get_timezone(self) -> str:
        return self.timezone

    async def set_timezone(self, timezone: str) -> None:
        self.timezone = timezone


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeWorkspace:
    def __init__(self, employees: FakeEmployeeRepository, uow: FakeUnitOfWork) -> None:
        self.employees = employees
        self.uow = uow


class FakeTenantScope:
    """One employee repository per tenant id, created on first reach.

    Modelling several stores is what makes multi-tenant switching testable
    without a database.
    """

    def __init__(self, tenants: FakeTenantRepository) -> None:
        self._tenants = tenants
        self.stores: dict[UUID, FakeEmployeeRepository] = {}
        self.uows: dict[UUID, FakeUnitOfWork] = {}

    def employees_at(self, tenant_id: UUID) -> FakeEmployeeRepository:
        return self.stores.setdefault(tenant_id, FakeEmployeeRepository())

    @asynccontextmanager
    async def for_tenant(self, tenant_id: UUID) -> AsyncIterator[FakeWorkspace]:
        tenant = self._tenants.by_id.get(tenant_id)
        if tenant is not None and tenant.status is not TenantStatus.ACTIVE:
            raise TenantNotActiveError()
        uow = self.uows.setdefault(tenant_id, FakeUnitOfWork())
        yield FakeWorkspace(self.employees_at(tenant_id), uow)


class FakeProvisioner:
    """Flips the tenant to ACTIVE like the real one, or fails on demand.

    Also seeds the Owner's ``Employee`` into that store — keyed by the
    master user id, as the real provisioner does.
    """

    def __init__(
        self,
        tenants: FakeTenantRepository,
        scope: FakeTenantScope,
        clock: FakeClock,
        fail: bool = False,
    ) -> None:
        self._tenants = tenants
        self._scope = scope
        self._clock = clock
        self.fail = fail
        self.calls: list[tuple[UUID, str, OwnerSeed | None]] = []

    async def provision(
        self, tenant_id: UUID, timezone: str, owner: OwnerSeed | None = None
    ) -> None:
        self.calls.append((tenant_id, timezone, owner))
        tenant = self._tenants.by_id[tenant_id]
        if self.fail:
            tenant.status = TenantStatus.FAILED
            raise ProvisioningFailedError(str(tenant_id))
        if owner is not None:
            self._scope.employees_at(tenant_id).by_id[owner.user_id] = Employee(
                id=owner.user_id,
                email=owner.email,
                full_name=owner.full_name,
                role=TenantRole.OWNER,
                is_active=True,
                created_at=self._clock.now(),
            )
        tenant.status = TenantStatus.ACTIVE
