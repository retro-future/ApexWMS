"""In-memory fakes for the application ports (PRD §9 Testing:
use cases are tested with no database at all)."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from application.dtos import RefreshTokenParts, UserWithRole
from application.errors import ProvisioningFailedError
from domain.entities import (
    Invitation,
    Membership,
    MembershipKey,
    RefreshTokenRecord,
    Tenant,
    User,
)
from domain.roles import Role
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
    def issue_access(self, user_id: UUID, tenant_id: UUID, role: Role) -> str:
        return f"access:{user_id}:{tenant_id}:{role.value}"

    def issue_refresh(self) -> RefreshTokenParts:
        secret = uuid4().hex
        return RefreshTokenParts(jti=uuid4(), secret=secret, token_hash=self.hash_opaque(secret))

    def new_opaque_secret(self) -> str:
        return uuid4().hex

    def hash_opaque(self, secret: str) -> str:
        return hashlib.sha256(secret.encode()).hexdigest()


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


class FakeTenantRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Tenant] = {}

    async def get(self, tenant_id: UUID) -> Tenant | None:
        return self.by_id.get(tenant_id)

    async def add(self, tenant: Tenant) -> None:
        self.by_id[tenant.id] = tenant

    async def update(self, tenant: Tenant) -> None:
        self.by_id[tenant.id] = tenant


class FakeMembershipRepository:
    def __init__(self, users: FakeUserRepository) -> None:
        self.items: dict[MembershipKey, Membership] = {}
        self._users = users

    async def get(self, key: MembershipKey) -> Membership | None:
        return self.items.get(key)

    async def list_for_user(self, user_id: UUID) -> list[Membership]:
        return [m for (uid, _), m in self.items.items() if uid == user_id]

    async def list_for_tenant(self, tenant_id: UUID) -> list[UserWithRole]:
        return [
            UserWithRole(user=self._users.by_id[uid], role=m.role)
            for (uid, tid), m in self.items.items()
            if tid == tenant_id
        ]

    async def count_owners(self, tenant_id: UUID) -> int:
        return sum(
            1
            for (_, tid), m in self.items.items()
            if tid == tenant_id and m.role is Role.OWNER
        )

    async def add(self, membership: Membership) -> None:
        self.items[membership.key] = membership

    async def update(self, membership: Membership) -> None:
        self.items[membership.key] = membership


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, RefreshTokenRecord] = {}

    async def get(self, jti: UUID) -> RefreshTokenRecord | None:
        return self.by_id.get(jti)

    async def add(self, record: RefreshTokenRecord) -> None:
        self.by_id[record.id] = record

    async def update(self, record: RefreshTokenRecord) -> None:
        self.by_id[record.id] = record

    async def revoke_all_for_user(self, user_id: UUID, tenant_id: UUID, now: datetime) -> None:
        for record in self.by_id.values():
            if (
                record.user_id == user_id
                and record.tenant_id == tenant_id
                and record.revoked_at is None
            ):
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


class FakeProvisioner:
    """Flips the tenant to ACTIVE like the real one, or fails on demand."""

    def __init__(self, tenants: FakeTenantRepository, fail: bool = False) -> None:
        self._tenants = tenants
        self.fail = fail
        self.calls: list[tuple[UUID, str]] = []

    async def provision(self, tenant_id: UUID, timezone: str) -> None:
        self.calls.append((tenant_id, timezone))
        tenant = self._tenants.by_id[tenant_id]
        if self.fail:
            tenant.status = TenantStatus.FAILED
            raise ProvisioningFailedError(str(tenant_id))
        tenant.status = TenantStatus.ACTIVE
