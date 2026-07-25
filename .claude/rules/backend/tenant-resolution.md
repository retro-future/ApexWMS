# Tenant resolution lives in one accessor service, never in a provider

Naming and authorizing "which tenant is this request for" is exactly the
kind of business logic `providers.md` forbids inside a `Provider`. It has
its own dedicated service, modeled on the reference `ICurrentTenantAccessor`
pattern (ASP.NET Core `IHttpContextAccessor`-backed resolver): one class,
constructed with its collaborators via DI, exposing resolution methods that
raise on failure — the provider only constructs it and calls a method.

## `CurrentTenantAccessor` (`infrastructure/current_tenant_accessor.py`)

Constructed from `Request`, `MasterSession`, `Settings`, and
`RequestBearerClaims` (the shared, memoized bearer-token decode also used by
`CurrentUserAccessor` — see below). Two public methods:

- `get_current_tenant() -> TenantContext` — the full, authorized resolution
  used by any tenant-scoped route. Two-tier fallback (PRD §3.3):
  1. `X-Tenant` header (slug or UUID) — wins if present;
  2. the JWT `tenant` claim, otherwise.

  Switching tenants via the header is only allowed where a
  `user_tenant_access` grant exists (`AuthorizationError` otherwise), and the
  resolved tenant must be `ACTIVE` with a live `tenant_databases` row
  (`TenantNotActiveError`). No header and no claim is `MissingTenantError`;
  a header/claim naming nothing real is `TenantNotFoundError`.

- `get_requested_tenant() -> RequestedTenant` — the loose, unauthorized
  header-only lookup used by anonymous routes (`/auth/login`,
  `/auth/refresh`) that merely *accept* a tenant hint. Never raises for an
  absent header; raises `TenantNotFoundError` for a header naming nothing
  real.

Everything else (`_resolve_tenant_model`, `_authorize_switch`,
`_by_slug_or_id`, `_header_value`) is a private method on this one class,
same as the C# reference keeps `ResolveTenantIdFromHttpContext`/
`FindTenantAsync`/`CheckSubscription` private on its single
`CurrentTenantAccessor`.

**If a third way to name a tenant is ever needed, extend this one class —
don't add a second resolution path anywhere else.**

## Related but distinct: `TenantScope`

`TenantScope`/`SqlTenantScope` (`application/ports/tenancy.py`,
`infrastructure/tenant_scope.py`) is a different concern: opening a *named*
tenant's database mid-request, after the tenant id is already known (e.g.
`ClaimsFactory` and `AcceptInvite`, where the tenant is discovered from a
just-read row rather than the request edge). `CurrentTenantAccessor` is
what resolves *which* tenant a request is for in the first place; it is
infrastructure/DI-boundary machinery with no application port, because its
output (`TenantContext`, carrying a raw `db_url`) is exactly the kind of
detail `application/` must never see. `TenantScope` is a proper application
port because what it hands back (`TenantWorkspace`: an `EmployeeRepository`
+ `UnitOfWork`) is fully abstract.

## `CurrentUserAccessor` (`infrastructure/security/current_user_accessor.py`)

The identity analogue, backing `AuthProvider`. Takes the same
`RequestBearerClaims` collaborator; `get_current_user() -> CurrentUser`
raises `AuthenticationError` if there's no bearer token, else builds
`CurrentUser` from the decoded claims via `permissions_for(...)`.

Sharing `RequestBearerClaims` between `CurrentUserAccessor` and
`CurrentTenantAccessor` means the bearer token is decoded at most once per
request, even though both identity and tenant resolution need it.
