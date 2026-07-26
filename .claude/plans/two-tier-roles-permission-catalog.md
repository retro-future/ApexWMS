# Two-Tier Roles, Permission Catalog & Tenant Resolution Chain

## Context

ApexWMS already implements database-per-tenant isolation end to end (M1 is complete despite
`CLAUDE.md` still claiming M0): `TenantEngineRegistry` LRU, per-request `TenantSession`,
`DefaultTenantProvisioner` state machine, migration fan-out CLI, JWT auth, invitations,
memberships. The LogisticsX C# reference (`C:\Users\Legion\multi-tenancy-architecture.md`)
describes the same shape, and comparing the two shows five of the eight requested features are
already present in equivalent or better form. Three are genuinely missing:

| # | Reference feature | ApexWMS today |
|---|---|---|
| 1 | DB-per-tenant + master pointer | ✅ `tenant_databases.db_name` + `tenant_db_url()` |
| 2 | **Two-tier roles + shared permission catalog** | ❌ only tenant `Role`; role checks are hard-coded role lists |
| 3 | Central `User` + multi-tenant join table | ✅ `User` (master) + `Membership` — strictly better than a nullable `TenantId` |
| 4 | **SuperAdmin as a plain user, seeded from config** | ❌ no platform tier at all |
| 5 | Structural master/tenant split | ✅ `MasterEntity`/`TenantEntity` markers + separate `MasterBase`/`TenantBase` |
| 6 | Invitation-accept onboarding | ✅ `InviteUser` / `AcceptInvite`, invitee sets own password |
| 7 | **Tenant resolution chain (api-key > header > claim)** | ❌ JWT claim only |
| 8 | **Server-stamped claim + `X-Tenant` switch** | ⚠️ claim stamped server-side, but no switching |

The outcome: a single namespaced permission catalog that both role tiers draw from, a platform
(SuperAdmin/Admin) role tier seeded from env, and per-request tenant resolution that lets a
multi-tenant user switch companies with an `X-Tenant` header — **validated against their
memberships**, closing the hole the reference doc itself flags at its end (lines 341–349).

### Decisions taken

- **Fixed roles + permission catalog.** PRD §2.1 is a fixed 4-role matrix and every later
  milestone's endpoints key off it. DB-driven per-tenant roles would push permission lookup into
  the tenant DB on every request and let each tenant's role set drift. Roles stay a `StrEnum`;
  what's new is the shared `Permission` catalog the two tiers both reference.
- **`X-Tenant` header, validated per request.** Costs one extra MasterDB query per request
  (tenant + membership); buys instant membership/role revocation and safe tenant switching.
- **Scope:** app roles + SuperAdmin seeding. No API keys (resolver tier 0 is left as a documented
  extension point), no admin-led `CreateTenant` — self-service `SignUp` (FR-1.1) stays the only
  onboarding path.
- **Point 5 needs no work.** `MasterBase` and `TenantBase` are separate `DeclarativeBase`
  subclasses with separate `metadata`, so a tenant table *cannot* land in the master schema —
  Python's ecosystem makes the .NET "prune pass" structurally unnecessary.

### Where Python forces a different approach than .NET

- **No reflection needed for the catalog.** The reference reflects over nested static classes at
  static-ctor time. A `StrEnum` already *is* an iterable catalog — `list(Permission)` replaces
  `Permission.GetAll()`, and mypy/ruff catch typos the C# `const string` approach cannot.
- **No Identity framework.** There is no `IdentityRole`/`user_roles` machinery, so the platform
  tier is one small `user_app_roles` table plus a `frozenset[AppRole]` on the principal.
- **Prefix collision-avoidance is enforced, not conventional.** The C# constructor rewrites names
  to add `app.`/`tenant.`. Here an import-time assertion in `domain/role_permissions.py` verifies
  tenant roles only reference `tenant.*` permissions and app roles only `platform.*` — a test
  would run too late to matter.
- **Per-request lookup is cheap here.** Resolution runs inside the already-open
  `MasterSession` (Dishka REQUEST scope), not a separate `DbContext` — no extra connection.
- Connection pooling, migration fan-out and async session-per-request are already solved
  (`TenantEngineRegistry`, `apexwms migrate --all-tenants`, `TenantDbProvider`).

---

## Implementation

### 1. Permission catalog & role maps (domain)

**New `backend/src/domain/permissions.py`** — one flat `StrEnum`, dotted values, two namespaces:

```python
class Permission(StrEnum):
    # tenant.* — granted by Membership.role, checked inside a tenant context
    USERS_MANAGE      = "tenant.users.manage"
    SETTINGS_MANAGE   = "tenant.settings.manage"
    LOCATIONS_MANAGE  = "tenant.locations.manage"
    CATALOG_MANAGE    = "tenant.catalog.manage"
    STOCK_RECEIVE     = "tenant.stock.receive"
    STOCK_SELL        = "tenant.stock.sell"
    STOCK_COUNT       = "tenant.stock.count"
    STOCK_WRITE_OFF   = "tenant.stock.write_off"
    PRICE_OVERRIDE    = "tenant.price.override"
    COST_VIEW         = "tenant.cost.view"          # PRD §2.1 note + FR-1.7
    ...
    # platform.* — granted by AppRole, never reachable inside a tenant context
    PLATFORM_TENANTS_MANAGE = "platform.tenants.manage"
    PLATFORM_ADMINS_MANAGE  = "platform.admins.manage"
```

Seed it with exactly the rows of the PRD §2.1 matrix (M2+ milestones append members here rather
than inventing ad-hoc role lists).

**New `backend/src/domain/app_roles.py`** — mirrors the existing `domain/roles.py`:

```python
class AppRole(StrEnum):
    SUPERADMIN = "platform.superadmin"
    ADMIN      = "platform.admin"
```

**New `backend/src/domain/role_permissions.py`** — the two independent maps plus the namespace
guard:

- `TENANT_ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]]` — transcribe PRD §2.1 column by
  column.
- `APP_ROLE_PERMISSIONS: Mapping[AppRole, frozenset[Permission]]` — `SUPERADMIN` = every
  `platform.*`; `ADMIN` = every `platform.*` except `PLATFORM_ADMINS_MANAGE`.
- `permissions_for(role)` / `permissions_for_app(roles)` helpers.
- Module-level assertion: every map is total over its enum, and no map crosses namespaces.

**New `backend/src/domain/entities/app_role_assignment.py`** — `AppRoleAssignment(MasterEntity)`,
composite `(user_id, app_role)`, modelled exactly on `domain/entities/membership.py` (including
the `NamedTuple` key). Export from `domain/entities/__init__.py`.

**Modify `backend/src/domain/entities/tenant.py`** — add `slug: str`, so `X-Tenant` can accept a
human-readable value as the reference does.

### 2. Tenant resolution chain (infrastructure)

**New `backend/src/infrastructure/tenant_resolution.py`**:

```python
@dataclass(frozen=True, slots=True)
class TenantRef:
    """What the edge asked for, before any authorization check."""
    value: str                                        # UUID string or slug
    source: Literal["api_key", "header", "claim"]

class TenantResolutionChain:
    """First hit wins: API key > X-Tenant header > JWT tenant claim (reference §4)."""
    def resolve(self, headers: Mapping[str, str], claim_tenant_id: UUID | None) -> TenantRef | None
```

Tier 0 (API key) is a documented `# not implemented in v1` branch — the ordering exists so adding
it later is a one-method change, not a restructure.

### 3. Validated tenant access (application)

**New `backend/src/application/use_cases/resolve_tenant_access.py`** — `ResolveTenantAccess`,
depending only on `TenantRepository` + `MembershipRepository` ports:

`execute(user_id, ref: TenantRef | None) -> CurrentUser`
1. No ref → `AuthenticationError` (or, for a platform user, the caller skips this entirely).
2. Look the tenant up by UUID or slug; `TenantNotActiveError` unless `ACTIVE`.
3. **Look up `MembershipKey(user_id, tenant.id)`; `AuthorizationError` if absent.** This is the
   check the reference doc admits it lacks.
4. Build `CurrentUser` with `role` and `permissions=permissions_for(role)` — the role comes from
   the *membership row*, never from the JWT, so a demotion takes effect on the next request.

**Modify `backend/src/application/ports/master/repositories.py`** — add
`TenantRepository.get_by_slug(slug) -> Tenant | None` and a new
`AppRoleRepository(Repository[AppRoleAssignment, AppRoleKey])` with
`list_for_user(user_id) -> list[AppRoleAssignment]`. Re-export from `application/ports/__init__.py`.

**Modify `backend/src/application/dtos.py`**:
- New `AuthenticatedUser(user_id, app_roles: frozenset[AppRole])` — the identity proven by the
  token, with no tenant.
- `CurrentUser` gains `permissions: frozenset[Permission]` and a `has(p) -> bool`.
  `tenant_id`/`role` stay non-optional, so every existing use case and router keeps working
  unchanged.
- `LoginResult` gains `app_roles` for the platform-user case.

### 4. Tokens & login for platform users

**Modify `backend/src/infrastructure/security/tokens.py`** — `AccessClaims.tenant_id: UUID | None`,
`role: Role | None`, plus `app_roles: frozenset[AppRole]`. A platform user's token carries **no
tenant claim at all** (reference line 271). Update `TokenService.issue_access` in
`application/ports/security.py` and `application/use_cases/token_issuer.py` to match.

**Modify `backend/src/application/use_cases/login.py`** — inject `AppRoleRepository`. A user with
no memberships but at least one app role gets a tenant-less token instead of
`InvalidCredentialsError`. Everything else (single membership → auto-select; several → return
`tenant_choices`) is unchanged and already better than the reference's `User.TenantId` default.

**Modify `backend/src/domain/entities/refresh_token.py` + its model** — `tenant_id` becomes
nullable for platform sessions. `RefreshTokens` (`application/use_cases/refresh_tokens.py`) must
re-read the membership role on refresh rather than trusting the old token.

### 5. DI wiring

**Rewrite `backend/src/di/providers/auth.py`** — currently one provider, now three REQUEST-scope
steps, each a single responsibility:

1. `AuthenticatedUser` ← bearer token (`JwtTokenService.decode_access`).
2. `TenantRef | None` ← `TenantResolutionChain.resolve(request.headers, claims.tenant_id)`.
3. `CurrentUser` ← `ResolveTenantAccess.execute(...)`.

`TenantDbProvider.tenant` in `di/providers/tenant_db.py` needs **no change** — it already depends
on `CurrentUser.tenant_id`, which is now the resolved-and-validated tenant. Register
`ResolveTenantAccess` in `di/providers/use_cases.py`, the app-role repo in
`di/providers/repositories.py`, and `TenantResolutionChain` (APP scope) in `di/providers/security.py`.

### 6. Authorization checks

**Rewrite `backend/src/presentation/security.py`** — `require(user, *permissions)` checking
`user.permissions`, plus `require_platform(principal, *permissions)` for the platform tier.
Update the three call sites in `presentation/routers/users.py` and
`presentation/routers/settings.py` from `require(current, Role.OWNER)` to
`require(current, Permission.USERS_MANAGE)` / `Permission.SETTINGS_MANAGE`. Same 403 behaviour,
same `presentation/errors.py` mapping — no new error types needed.

### 7. Persistence & migration

- **New** `infrastructure/persistence/master/models/app_role_assignment.py` (`user_app_roles`:
  `user_id`, `app_role`, composite PK) — modelled on `models/membership.py`.
- **New** `infrastructure/persistence/master/repositories/app_role_assignment.py`, extending
  `MasterCrudRepository` like `repositories/membership.py`.
- **Modify** `models/tenant.py` (+`slug`, unique index) and `repositories/tenant.py`
  (`get_by_slug`), `models/refresh_token.py` (nullable `tenant_id`).
- **New migration** `infrastructure/persistence/migrations/master/versions/0002_app_roles_and_tenant_slug.py`
  — creates `user_app_roles`, adds `tenants.slug` (backfilled from `name`, then `NOT NULL` +
  unique), makes `refresh_tokens.tenant_id` nullable. **Master-only** — no tenant migration, so
  no fan-out is required for this change.
- **Modify** `application/use_cases/sign_up.py` to generate a unique slug from `tenant_name`
  (slugify + numeric suffix on collision).

### 8. SuperAdmin seeding

**Modify `backend/src/infrastructure/config.py`** — `superadmin_email: str | None`,
`superadmin_password: str | None`, `superadmin_full_name: str = "Platform Owner"`,
`seed_superadmin_on_startup: bool = False`. Document in `backend/.env.example`.

**New `backend/src/infrastructure/seeding.py`** — `SuperAdminSeeder.seed()`, idempotent in the
reference's shape: if any user already holds `AppRole.SUPERADMIN`, return; else find-or-create the
user by email (argon2 hash via the existing `Argon2PasswordHasher`) and insert the assignment.
No SuperAdmin table — just a `User` plus a row in `user_app_roles`.

**Modify `backend/src/infrastructure/cli.py`** — add `apexwms seed-superadmin`, following the
existing `retry-provisioning` subcommand shape. `presentation/app.py`'s lifespan calls the seeder
only when `seed_superadmin_on_startup` is true, so `create_app()` stays side-effect-free by
default.

### 9. Tests

- `tests/domain/test_permissions.py` — the two maps are total, namespaces never cross, and each
  role's set matches the PRD §2.1 row.
- `tests/application/test_tenant_resolution.py` — header wins over claim; unknown slug → 404-ish;
  **`X-Tenant` naming a tenant the user has no membership in → `AuthorizationError`**; non-ACTIVE
  tenant → `TenantNotActiveError`; role reflects a membership changed since the token was issued.
- `tests/api/test_tenant_switch.py` — a two-membership user hits the same endpoint with two
  different `X-Tenant` values and one unchanged token, and sees each tenant's own data.
- `tests/api/test_superadmin.py` — seeding is idempotent; a platform user logs in and gets a token
  with no tenant claim; that token is rejected on tenant-scoped endpoints.
- Extend `tests/api/test_role_matrix.py` to drive off `TENANT_ROLE_PERMISSIONS`, and add app-role
  fakes to `tests/application/fakes.py`.
- `tests/api/test_tenant_isolation.py` (FR-1.4) must still pass untouched — it is the regression
  guard for this whole change.

### 10. Documentation

**`CLAUDE.md`** — correct "the codebase is at M0" to M1-complete; add a *Roles & permissions*
subsection (two tiers, one catalog, the namespace invariant), rewrite the multi-tenancy section's
request lifecycle to the resolver chain, note that `MasterBase`/`TenantBase` is what enforces the
entity split, and note that `ports/master/` vs `ports/tenant/` mirrors it.

**`docs/prd.md`** — §2 gains a *Platform roles* subsection and the `Permission` catalog table;
§2.1 gains the permission id per row; §3.3 replaces the lifecycle block with the resolution chain;
§5.1 gains FR-1.8 (`X-Tenant` switching, validated against membership), FR-1.9 (platform users /
SuperAdmin, no tenant claim); §8 gains no new routes; §10's M1 row is marked delivered and its
scope extended to cover the role tier.

---

## Verification

```bash
docker compose up -d                                   # repo root
cd backend
uv run apexwms migrate-master                          # applies 0002
uv run pytest                                          # full suite, incl. FR-1.4 isolation test
uv run ruff check src tests

APEXWMS_SUPERADMIN_EMAIL=root@apex.local \
APEXWMS_SUPERADMIN_PASSWORD=... uv run apexwms seed-superadmin
uv run apexwms seed-superadmin                         # second run must be a no-op
```

End-to-end, with `uv run uvicorn main:app --reload`:

1. `POST /api/v1/auth/signup` twice → tenants A and B; note each `slug`.
2. `POST /api/v1/users/invite` in A for `dual@example.com`; `POST /api/v1/auth/accept-invite`.
3. `POST /api/v1/users/invite` in B for the same email; accept → the user now has two memberships.
4. `POST /api/v1/auth/login` with no `tenant_id` → `tenant_choices` returned, no tokens.
5. Log in selecting A. With that **one unchanged token**, call `GET /api/v1/auth/me` with
   `X-Tenant: <slug-A>` then `X-Tenant: <slug-B>` → different `tenant_id` and role each time.
6. Same token with `X-Tenant: <slug of a tenant they don't belong to>` → **403**, no data.
7. Log in as the seeded SuperAdmin → token has no tenant claim; any tenant-scoped endpoint → 401/403.
8. Demote the user's role in A via `PATCH /users/{id}/role`, then re-issue the same request with
   the *old* token → the new role is in force immediately.
