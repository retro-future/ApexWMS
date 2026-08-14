# Multi-tenancy: database-per-tenant (PRD §3)

This is the most consequential and expensive-to-reverse decision in the
codebase — do not casually add a `tenant_id` column or a cross-tenant query
as a shortcut.

- **MasterDB** — the tenant registry (`tenants` with a unique `slug`,
  `tenant_databases`) **and platform identity**: `users`, `user_app_roles`,
  `user_tenant_access`, `invitations`, `refresh_tokens`. No operational data
  ever.
- **TenantDB** — one physical database per store: all business data plus
  `employees` (who works here, in what role). **No `tenant_id` column
  exists inside a tenant database** — isolation is physical, not a `WHERE`
  filter. A missing filter cannot leak another store's data because that
  data isn't in the connected database.
- **Identity is split, deliberately.** `User` (MasterDB, email unique
  platform-wide) is *who someone is*; `Employee` (TenantDB) is *what they
  may do at one store*. One person, one login, potentially several
  `Employee` rows with different roles.
- **`Employee.id` IS the master `User.id`** — not a fresh uuid, and no FK
  can enforce it across databases. It's what lets M3's
  `stock_movements.user_id` be a real tenant-local foreign key while login
  stays central. `employees.email`/`full_name` are denormalized copies so
  tenant-side reads never cross databases; MasterDB wins on conflict.
  `tests/architecture/test_database_split.py` guards all of this.
- **Two role namespaces** (`domain/roles.py`): `AppRole` (`app.superadmin`,
  `app.admin`, on `user_app_roles`) and `TenantRole`
  (`tenant.owner|manager|storekeeper|seller`, on `employees.role`). The
  prefixes are collision-avoidance — the string spaces cannot overlap. A
  SuperAdmin is just a `User` with `tenant_id = NULL` and an app role.
- **Authorization is permissions, not roles** (`domain/permissions/`): one
  flat `Permission.<Module>.<Action>` `StrEnum` (`catalog.py`), with
  `AppRolePermissionProvider`/`TenantRolePermissionProvider`
  (`providers.py`) assigning subsets and `PermissionEvaluator`
  (`evaluator.py`) resolving the union. Values are wire format — add
  members, never rename one. Routers call `require(current,
  Permission.USERS_MANAGE)` / `require_any(...)` from
  `presentation/security.py`, which raise `AuthorizationError` (403)
  against `CurrentUser.permissions`. PRD §2.1 is not hierarchical, so never
  compare role rank. Note `PRICING_SET` (stating what the store asks for a
  model or a handset) and `PRICING_OVERRIDE` (negotiating one invoice line)
  are separate acts, not one permission.
- **Tenants are created by SuperAdmin CLI only** (`apexwms create-tenant`,
  `create-superadmin`), never self-service — there is no sign-up endpoint.
  Provisioning writes the master `users` row, then seeds the matching
  `employees` row with a temporary password and `must_change_password`.
- **Login names no tenant.** Credentials authenticate against MasterDB; the
  `tenant` claim is stamped server-side by `ClaimsFactory`
  (`application/services/claims.py`) from `users.tenant_id`, or from
  `X-Tenant` when the user has access. A platform operator's token carries
  **no** tenant claim at all.
- Request lifecycle: tenant resolved from **`X-Tenant` header > JWT
  `tenant` claim** → looked up in MasterDB, must be `active` →
  `TenantEngineRegistry.get(...)` (LRU, opens engine on miss) →
  `AsyncSession` at Dishka `REQUEST` scope → the handler executes, never
  knowing a tenant exists → session committed/closed by the container. Full
  resolution logic: [tenant-resolution.md](tenant-resolution.md).
- **The header wins over the claim** — that's what lets a multi-store user
  switch without re-authenticating — but it is *authorized*, not trusted:
  no `user_tenant_access` grant means `403` before any session opens. All
  in `di/providers/tenant_db.py`; no middleware, and nothing parses the
  request body.
- The tenant is resolved **once, at the edge**. Nothing in `domain` or
  `application` takes a tenant parameter. Two narrow exceptions:
  `ResolvedTenantId` is injected where a collaborator must stamp it
  (`InviteUser`), and `TenantScope` (`infrastructure/tenant_scope.py`)
  opens a store's database when the edge couldn't have known it — login,
  which learns the tenant only after reading the master user row.
- `infrastructure/tenancy.py` implements `TenantEngineRegistry`: a bounded
  LRU cache of `AsyncEngine`s (`APEXWMS_MAX_LIVE_TENANT_ENGINES`, default
  50; `APEXWMS_TENANT_POOL_SIZE`, default 5 connections each). Evicted
  engines are disposed. This ceiling is intentional — beyond it, the answer
  is PgBouncer or a shared-schema rethink, not a bigger cache.
- `TenantContext` (tenant_id + db_url) is built in `TenantDbProvider.tenant`
  from the request plus a MasterDB lookup. If a third way to name a tenant
  is ever needed, extend that one resolver — don't add a second path.

## Dishka DI scopes (PRD §7.5)

- **`APP`** scope: `Settings`, `MasterEngine`, `TenantEngineRegistry`,
  `JwtTokenService`, `PasswordHasher`, `TenantProvisioner`. Later: PDF
  renderer.
- **`REQUEST`** scope: `MasterSession`,
  `TenantContext`/`TenantEngine`/`TenantSession`, `ResolvedTenantId`,
  `RequestedTenant`, `CurrentUser`, `TenantScope`, repositories, units of
  work, command/query handlers.

Identity repositories take `MasterSession`; only `EmployeeRepository` and
`TenantSettingsRepository` take `TenantSession`. Getting that wrong is the
single easiest way to reintroduce the bug this architecture exists to
prevent.

`MasterEngine`, `MasterSession`, `TenantEngine`, `TenantSession` are
`NewType`-wrapped `AsyncEngine`/`AsyncSession` (`infrastructure/types.py`)
purely so the container can't hand a repository the wrong database — keep
using these aliases (not bare `AsyncEngine`/`AsyncSession`) whenever wiring
new providers that touch either database.

**A `NewType` is an identity function at runtime, so `uv run ty check` is
the only thing that enforces any of this** — ruff does not type-check, and
no test can catch a master session handed to a tenant repository. Treat a
red `ty check` as a broken build. Code that hand-wires repositories outside
the container (`infrastructure/cli.py`) must wrap its session explicitly:
`MasterSession(session)`, never a bare `AsyncSession`. `tests/` is
currently outside the checked set — the domain suites assert that invalid
calls are rejected, and those lines carry mypy-style `# type: ignore[...]`
codes ty doesn't recognise.

Settings enter the container via `from_context` + `context={Settings:
...}` in `create_container()`, not a provider that closes over a
constructor argument — follow that pattern for other request-scoped
context values.
