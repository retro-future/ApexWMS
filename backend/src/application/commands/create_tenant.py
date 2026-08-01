"""A SuperAdmin creates a store and its Owner (PRD §3.4).

This replaces public sign-up: a tenant exists because an operator decided
it should. The Owner gets a master ``User`` with a generated temporary
password, and provisioning seeds the matching ``Employee`` into the new
store's database — same id on both, which is the equality the ledger's
foreign keys depend on from M3.

CLI-only: there is no HTTP surface that creates a tenant (PRD §3.4).
"""

from uuid import UUID, uuid4

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import OwnerSeed
from application.errors import AlreadyMemberError, SlugAlreadyTakenError
from application.ports import (
    Clock,
    MasterUnitOfWork,
    PasswordHasher,
    TenantProvisioner,
    TenantRepository,
    TokenService,
    UserRepository,
)
from application.services import SlugNormalizer, TimezoneValidator
from domain.entities import Tenant, User
from domain.enums import TenantStatus


class CreateTenantData(CamelModel):
    """The temporary password exists only here — it is never stored in plaintext."""

    tenant_id: UUID
    slug: str
    owner_email: str
    owner_user_id: UUID
    temporary_password: str


class CreateTenantCommand(Command[ResultWithData[CreateTenantData]]):
    name: str
    slug: str
    owner_email: str
    owner_full_name: str
    timezone: str


class CreateTenantHandler(
    IRequestHandler[ResultWithData[CreateTenantData], CreateTenantCommand]
):
    def __init__(
        self,
        tenants: TenantRepository,
        users: UserRepository,
        hasher: PasswordHasher,
        tokens: TokenService,
        provisioner: TenantProvisioner,
        clock: Clock,
        uow: MasterUnitOfWork,
        slugs: SlugNormalizer,
        timezones: TimezoneValidator,
    ) -> None:
        self._tenants = tenants
        self._users = users
        self._hasher = hasher
        self._tokens = tokens
        self._provisioner = provisioner
        self._clock = clock
        self._uow = uow
        self._slugs = slugs
        self._timezones = timezones

    async def handle(
        self, request: CreateTenantCommand
    ) -> ResultWithData[CreateTenantData]:
        self._timezones.validate(request.timezone)
        slug = self._slugs.normalize(request.slug)
        if await self._tenants.get_by_slug(slug) is not None:
            raise SlugAlreadyTakenError(slug)

        owner_email = request.owner_email.strip().lower()
        # Email is unique platform-wide now, so an existing person cannot be
        # made the Owner this way — invite them into the store instead.
        if await self._users.get_by_email(owner_email) is not None:
            raise AlreadyMemberError(owner_email)

        now = self._clock.now()
        tenant = Tenant(
            id=uuid4(),
            name=request.name,
            slug=slug,
            status=TenantStatus.PENDING,
            created_at=now,
        )
        await self._tenants.add(tenant)

        temporary_password = self._tokens.new_opaque_secret()
        owner = User(
            id=uuid4(),
            email=owner_email,
            full_name=request.owner_full_name,
            password_hash=self._hasher.hash(temporary_password),
            tenant_id=tenant.id,
            is_active=True,
            must_change_password=True,
            created_at=now,
        )
        await self._users.add(owner)
        # Commit before provisioning: the pending tenant and its Owner must
        # survive a provisioning crash so the operation is retryable (§3.4).
        await self._uow.commit()

        await self._provisioner.provision(
            tenant.id,
            request.timezone,
            OwnerSeed(user_id=owner.id, email=owner.email, full_name=owner.full_name),
        )

        return ResultWithData[CreateTenantData].succeed_with_data(
            CreateTenantData(
                tenant_id=tenant.id,
                slug=slug,
                owner_email=owner_email,
                owner_user_id=owner.id,
                temporary_password=temporary_password,
            )
        )
