# Correct the identity split: port LogisticsX's multi-tenancy model to ApexWMS

## Context

### The mistake being corrected

The previous change moved **all** identity into TenantDB — one `users` table per tenant carrying
login credentials *and* role — and deleted master-side identity entirely. That conflates two things
LogisticsX deliberately keeps apart (`multi-tenancy-architecture.md` §1, §5):

> "who is this person" (`User`, master DB, one row ever) is separate from "what can they do in
> company X" (`Employee` + `TenantRole`, tenant DB, one row per company they work for)

Consequences of getting this wrong: no multi-tenant users, no SuperAdmin data model at all, login
forced to name a tenant before it could authenticate, and email uniqueness scoped per-tenant so the
same person at two stores became two unrelated accounts.

**Why the earlier reasoning was wrong.** I argued identity had to live tenant-side so M3's
`stock_movements.user_id` could be a real foreign key. LogisticsX dissolves that with
`Employee.Id == User.Id` (`Employee.CreateEmployeeFromUser(owner)`, then
`Repository<Employee>().GetByIdAsync(user.Id)`): the tenant DB holds a *mirror* row keyed by the
master user id. Ledger FKs point at tenant-local `employees.id` — enforceable, joinable — while the
login identity stays central. Both properties, no trade.

### Source-of-truth conflict, and how it was resolved

The two reference docs disagree. `multi-tenancy.md` (LogisticsX's own overview) lists "Users, roles,
invitations" under *Tenant database*. `multi-tenancy-architecture.md` shows the actual entity code
putting `User`, `AppRole`, `UserTenantAccess` and `Invitation` in **master**. Per instruction the
architecture doc is authoritative; the overview doc is a simplification. `Invitation` in particular
is master-side on purpose — "stored centrally so acceptance doesn't require picking a tenant DB first."

### Decisions (confirmed)

1. **Master-based login.** Email+password authenticate against master `users`; the tenant claim is
   stamped server-side from `User.tenant_id` (the port of `UserCustomClaimsFactory`). No tenant
   header at login.
2. **Port the permission catalog** — `Permission.<Module>.<Action>` + `APP_ROLE_PERMISSIONS` /
   `TENANT_ROLE_PERMISSIONS` maps. PRD §2.1 is already a permission matrix.
3. **Master scope: identity only.** Subscription/billing, API keys, feature flags and impersonation
   stay documented-but-unbuilt.
4. **`Employee`** is the tenant-side entity name.

---

## Target model

### Database split (both 0001 migrations rewritten in place — nothing has shipped)

| MasterDB | TenantDB |
|---|---|
| `tenants` (id, name, slug, status, created_at) | `employees` (id = users.id, email, full_name, role, is_active, created_at) |
| `tenant_databases` | `locations` |
| `users` (id, email **globally unique**, full_name, password_hash, `tenant_id` **nullable**, is_active, must_change_password, created_at) | `tenant_settings` |
| `user_app_roles` (user_id, role) — mirrors Identity's `user_roles` join | |
| `user_tenant_access` (user_id, tenant_id) — one user, many tenants | |
| `invitations` (id, email, `tenant_id` nullable, `tenant_role` nullable, `app_role` nullable, type, token_hash, expires_at, accepted_at, created_by) | |
| `refresh_tokens` (id, user_id, token_hash, expires_at, revoked_at, replaced_by) | |

`refresh_tokens` moves to master because login is now master-based — the token belongs to the master
`User`, as it does in LogisticsX where IdentityServer issues centrally. **No TenantDB table gains a
`tenant_id`**; isolation stays physical.

`employees` duplicates `email`/`full_name` from `users`. Deliberate denormalization, matching
`CreateEmployeeFromUser` — tenant-side user lists and (from M3) ledger joins never need a
cross-database read. Master is the source of truth on conflict.

### Two namespaced role systems (`domain/roles.py`)

- `AppRole`: `app.superadmin`, `app.admin` — master, on `user_app_roles`.
- `TenantRole`: `tenant.owner`, `tenant.manager`, `tenant.storekeeper`, `tenant.seller` — tenant, on
  `employees.role`.

Prefixes are the collision-avoidance mechanism and are carried literally in the enum values, with a
module-level guard asserting every member starts with its namespace (the port of the C# constructors'
`if (!name.StartsWith("app."))`).

### Permission catalog (`domain/permissions.py`)

Nested classes of string constants as "modules", plus `Permission.all()` reflecting over them via
`vars()` — the direct analogue of the C# nested-static-class + reflection scheme. Modules come
straight from PRD §2.1: `Users`, `TenantSettings`, `Location`, `Catalog`, `PurchaseOrder`,
`Receiving`, `Cost`, `Sales`, `Pricing`, `CreditSale`, `CreditCompany`, `Payment`,
`CustomerAccount`, `SupplierReturn`, `StockCount`, `WriteOff`, `Document`, `Scan`, `Reporting`,
`FinancialLedger`, plus app-level `Tenant` and `AppRole`.

Two independent maps assign subsets of that one catalog:
`APP_ROLE_PERMISSIONS` (superadmin → everything; admin → everything except `AppRole.Manage`) and
`TENANT_ROLE_PERMISSIONS` (the four §2.1 columns). Both expose `register_role(name, func)` for the
dynamic-roles path the reference describes.

`presentation/security.py::require` changes from `require(current, Role.OWNER)` to
`require(current, Permission.Users.Manage)`; `CurrentUser` carries a resolved
`permissions: frozenset[str]`.

### Tenant resolution — two tiers, header wins

LogisticsX resolves MCP key > `X-Tenant` header > JWT claim. ApexWMS has no MCP, so tier 0 is
dropped and the header/claim asymmetry is preserved: **header wins over claim**, which is what lets a
multi-tenant user switch companies without re-authenticating.

Rename `X-Tenant-Slug` → **`X-Tenant`**, accepting either a slug or a UUID (`TenantRepository` gains
the UUID branch alongside the existing `get_by_slug`).

The reference flags its own weak spot here — "there's no separate authorization check gating 'may
this JWT use this X-Tenant value' … worth strengthening in ApexWMS: consider validating the header's
tenant against `UserTenantAccess`". We take that advice: when a header names a tenant other than the
token's claim, the resolver checks `user_tenant_access` (or `users.tenant_id`) and returns **403** if
the user has no grant, rather than relying on the tenant DB coming back empty.

All of this lives in `di/providers/tenant_db.py`, still with no middleware.

### `TenantScope` — the port of `SetCurrentTenantByIdAsync`

Login must read the `Employee` from a tenant DB it only discovers *after* reading the master `User`,
so the request-scoped `TenantSession` (which needs the tenant up front) doesn't fit. New
APP-scoped port `application/ports/tenancy.py::TenantScope`:

```python
async def for_tenant(self, tenant_id: UUID) -> AsyncContextManager[TenantWorkspace]
```

`TenantWorkspace` exposes `employees` + `uow`. The infrastructure implementation reuses the existing
`TenantEngineRegistry` (`infrastructure/tenancy.py`) and the master `tenant_databases` lookup —
no new connection machinery. Used by `Login` (stamp the role claim), `AcceptInvite` (create the
`Employee` in the invited tenant), and available to the CLI.

### Claims factory

`application/use_cases/claims.py` ports `UserCustomClaimsFactory`: given a `User` and an optional
header-supplied tenant, resolve `tenant_id = header ?? user.tenant_id`; if it is `None` the subject
is an app-level user and **no tenant claim is issued at all**; otherwise load the `Employee` through
`TenantScope` and stamp `tenant` + tenant-role claims alongside any app-role claims. JWT payload
gains `app_roles` and makes `tenant`/`role` optional (`infrastructure/security/tokens.py`).

---

## Files to change

Broadly: every module the previous change touched, in reverse. Representative paths per layer —
the pattern repeats rather than needing enumeration.

- **Migrations** — `persistence/migrations/{master,tenant}/versions/0001_*.py`, rewritten in place.
- **Domain** — `roles.py` (split), new `permissions.py`, new `entities/employee.py`,
  `entities/user.py` → master + nullable `tenant_id`, `entities/invitation.py` +
  `entities/refresh_token.py` → `MasterEntity`, new `entities/user_tenant_access.py` and
  `entities/user_app_role.py`.
- **Application** — ports move back: `ports/master/repositories.py` gains `UserRepository`,
  `RefreshTokenRepository`, `InvitationRepository`, `UserTenantAccessRepository`;
  `ports/tenant/repositories.py` keeps `EmployeeRepository` + settings. New `ports/tenancy.py`.
  `use_cases/login.py` rewritten against master + `TenantScope`; new `use_cases/claims.py`;
  `accept_invite.py`, `invite_user.py`, `list_users.py`, `change_user_role.py`, `get_me.py`,
  `change_password.py`, `create_tenant.py` repointed.
- **Infrastructure** — models/repositories move back under `persistence/master/`, with
  `persistence/tenant/{models,repositories}/employee.py` new; `provisioning.py` seeds an `Employee`
  (not a user row) from `OwnerSeed`; `tenancy.py` gains the `TenantScope` implementation;
  `cli.py` gains `create-superadmin`.
- **Presentation** — `security.py` switches to permissions; `routers/auth.py` login/refresh/accept-invite
  drop the tenant-header requirement; `schemas/*` follow.
- **DI** — `providers/tenant_db.py` (two-tier resolution + access validation), `providers/auth.py`
  (permissions on `CurrentUser`), `providers/repositories.py`, `providers/use_cases.py`.

### Structural guard — the port of `PruneTenantOnlyTypesForMaster`

C# strips accidentally-included tenant types out of the master model by reflection. SQLAlchemy's two
separate `DeclarativeBase`s (`MasterBase`/`TenantBase`) already make the mixing impossible at
runtime, so the port is the *check*, as a test — new `tests/architecture/test_database_split.py`:

- every class mapped on `MasterBase` maps to a domain entity marked `MasterEntity`, and vice versa;
- no table on `TenantBase` has a `tenant_id` column;
- `employees` and `users` agree on primary-key type (the `Employee.Id == User.Id` contract).

---

## Deliberate deviations from the C# reference

Called out here so the summary at the end has a single source:

| LogisticsX | ApexWMS | Why |
|---|---|---|
| ASP.NET Identity (`IdentityUser`/`IdentityRole`, `UserManager`) | Plain tables + existing argon2 `PasswordHasher` | No Identity equivalent in this stack. The `user_roles` join is ported as `user_app_roles`. |
| `TenantRole` as a **table** with `TenantRoleClaim` | `TenantRole` **enum**, role name on `employees.role` | Mirrors what LogisticsX actually exercises ("all tenants share the same 5 `TenantRoles`"), and PRD §2.1 fixes ApexWMS's four. The reference's dynamic-roles path is documented as the upgrade. |
| Reflection-driven `OnModelCreating` + prune pass | Two `DeclarativeBase`s + an architecture test | Separate metadata makes leakage structurally impossible; the test ports the *intent* of the prune guard. |
| `Tenant.ConnectionString` stored per row | `tenant_databases.db_name` + derive from master URL | Avoids duplicating credentials into every tenant row. Existing `tenant_db_url()` already does this. |
| 3-tier resolution (MCP key first) | 2-tier (`X-Tenant` header > JWT claim) | ApexWMS has no MCP server. Tier ordering and the header-wins asymmetry are preserved. |
| Header trusted without an access check | Header validated against `user_tenant_access` → 403 | The reference explicitly recommends this hardening for ApexWMS. |
| Temp password emailed, no forced reset | Temp password + `must_change_password` enforced | Also the reference's own recommendation ("worth hardening in ApexWMS if you copy this"). |
| `CustomerUser`, `ApiKey`, `Impersonation*`, `Subscription*`, feature flags | Not built | Out of scope per decision 3; no ApexWMS feature reads them. |

---

## Verification

```bash
docker compose up -d
cd backend
uv run ruff check src tests
uv run pytest
uv run pytest tests/architecture tests/api/test_tenant_isolation.py -v
```

Cheap gate while wiring: `uv run python -c "from presentation.app import create_app; create_app()"`.

End to end — note host port 5432 is occupied by a native Postgres, so use a throwaway container
(`-p 55433:5432`) as in the last round:

```bash
uv run apexwms migrate-master
uv run apexwms create-superadmin --email ops@apexwms.uz --name "Ops"
uv run apexwms create-tenant --name "Acme Phones" --slug acme --owner-email owner@acme.uz --owner-name "Acme Owner"
uv run apexwms create-tenant --name "Beta Mobile" --slug beta --owner-email owner@beta.uz --owner-name "Beta Owner"
```

1. `POST /auth/login` with **no tenant header** → tokens; the `tenant` claim was stamped from
   `users.tenant_id`; `must_change_password: true`.
2. SuperAdmin login → succeeds, JWT carries **no** `tenant` claim, `app_roles: ["app.superadmin"]`.
3. `GET /users` with Acme's token → Acme's employees only.
4. Same token + `X-Tenant: beta` → **403** (no `user_tenant_access` grant), not 200-with-empty.
5. Grant access (`user_tenant_access` row), re-issue, then `X-Tenant: beta` → succeeds and returns
   Beta's employees — multi-tenant switching without re-authenticating.
6. `X-Tenant: <beta-uuid>` behaves identically to the slug.
7. Invite + accept without any tenant header (invitation is master-side) → `employees` row appears in
   Acme's DB with `id` equal to the new `users.id`; confirm in psql.
8. A Storekeeper token is refused `POST /users/invite` (`Permission.Users.Manage`) and allowed
   `POST /receipts`-class permissions per §2.1.
9. `psql`: master holds `users`/`invitations`/`refresh_tokens`; each tenant DB holds `employees` and
   no `tenant_id` column anywhere.

---

## Documentation to update after the code

- **`docs/prd.md`** — §2 (SuperAdmin as an `app.` role, not a separate entity; the §2.1 matrix
  becomes the permission catalog's source), §3.1 (the split table), §3.3 (two-tier resolution,
  header wins, access-validated), §3.4 (provisioning seeds an `Employee`), §3.5 (rewrite: this
  correction and its rationale, replacing the previous turn's "users are per-tenant" argument),
  §5.1 (FR-1.2 no longer names a tenant; **FR-1.3 returns** — multi-tenant users via
  `user_tenant_access`), §8 (`X-Tenant` optional, not required on auth routes).
- **`CLAUDE.md`** — last. Rewrite the multi-tenancy bullets: master = registry **+ identity**,
  tenant = business data + `employees`; `Employee.id == User.id`; two role namespaces; permission
  catalog; two-tier resolution with the access check.
