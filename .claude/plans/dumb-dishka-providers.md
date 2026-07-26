# Dumb Dishka providers + provide_all use cases + repo-provider split

## Context

`di/providers/tenant_db.py` and `di/providers/auth.py` currently do real work inside `@provide` methods: `TenantDbProvider` has a `@staticmethod _resolve` that decodes JWTs, queries MasterDB, and raises `MissingTenantError`/`TenantNotFoundError`/`AuthorizationError`/`TenantNotActiveError`; `AuthProvider.current_user` decodes a bearer token and raises `AuthenticationError` inline. This violates the principle (confirmed by the user, using a C# `CurrentTenantAccessor` reference class as the conceptual model) that Dishka providers must only construct/wire objects — all resolution logic, validation, and exception-raising belongs in dedicated service classes in their proper architectural layer.

Separately: `di/providers/use_cases.py` hand-writes a factory method per use case purely to wire ports together — `provide_all` (dishka's batch-registration helper, confirmed via docs) eliminates this boilerplate via automatic constructor-based injection, *provided* every constructor parameter's type is itself DI-resolvable. Two use cases (`TokenIssuer`, `InviteUser`) currently take bare `timedelta`/`UUID` params that a human factory fills in from `Settings` — these must become distinct `NewType`s so dishka can resolve them unambiguously. `di/providers/repositories.py` mixes MasterDB- and TenantDB-scoped repositories in one class and needs to split along that line.

Two scope decisions already confirmed with the user:
1. Bring `AuthProvider` into compliance too (not just `TenantDbProvider`), since it has the identical anti-pattern.
2. While doing so, deduplicate the bearer-token decode that today happens independently in both `AuthProvider` and `TenantDbProvider` (once per request instead of twice).

## Architectural note (falls out of the provide_all requirement)

`InviteUser.tenant_id` is typed `UUID` and `TokenIssuer.refresh_ttl`/`InviteUser.invite_ttl` are typed plain `timedelta` today — the existing `di/providers/use_cases.py` factory bridges the DI-side `ResolvedTenantId` `NewType` (defined in `infrastructure/types.py`) down to a plain `UUID` positionally. For `provide_all` to auto-resolve these via reflection, the *use case's own* constructor must be annotated with the distinguishing `NewType`s — but `application/` may not import `infrastructure/types.py` (dependency rule). Since these NewTypes are pure `UUID`/`timedelta` wrappers with zero infra coupling, the fix is to move `ResolvedTenantId` into a new `application/types.py` (application may own this) and add `RefreshTokenTtl`/`InviteTtl` alongside it. `infrastructure/types.py` keeps only the session/engine NewTypes; infra code importing `ResolvedTenantId` now imports it from `application.types` (infra → application is an allowed direction).

## Changes

### 1. `.claude/rules/backend/` — new rule docs
Three files:
- **`providers.md`** — providers may only construct/wire objects; at most trivial conditionals (e.g. picking an implementation); no private/static/classmethod helpers on a `Provider` subclass (extract to a real class instead); no business logic or exception raising inside `@provide` methods — delegate to a service.
- **`tenant-resolution.md`** — documents the `CurrentTenantAccessor` pattern (below) as the one resolver for naming/authorizing a tenant, modeled on the attached C# `CurrentTenantAccessor` reference (header → claim fallback, private helper methods for each resolution step, exceptions raised from the service not the caller). References `infrastructure/current_tenant_accessor.py` and the existing `TenantScope`/`SqlTenantScope` pattern as the precedent this follows.
- **`exception-handling.md`** — application errors (`ApplicationError` subclasses) are raised only from services/use cases/domain-adjacent helpers that own the business rule being violated, never from a `Provider` method or DI wiring code.

### 2. `application/types.py` (new)
```python
ResolvedTenantId = NewType("ResolvedTenantId", UUID)
RefreshTokenTtl = NewType("RefreshTokenTtl", timedelta)
InviteTtl = NewType("InviteTtl", timedelta)
```
Remove `ResolvedTenantId` from `infrastructure/types.py` (keep only `MasterEngine`/`MasterSession`/`TenantEngine`/`TenantSession`). Update every importer of `ResolvedTenantId` (`di/providers/tenant_db.py`, `di/providers/use_cases.py` → now unused there) to pull from `application.types`.

### 3. Shared claims decode — `infrastructure/security/request_claims.py` (new)
`RequestBearerClaims`: constructed from `Request` + `JwtTokenService`; `.get() -> AccessClaims | None`, memoized per instance (REQUEST-scoped ⇒ once per request). Returns `None` for an absent/non-bearer `Authorization` header; still raises `InvalidTokenError` (via `JwtTokenService.decode_access`) for a malformed *present* token — matching today's `_claims()` behavior in `tenant_db.py`.

### 4. `infrastructure/security/current_user_accessor.py` (new)
`CurrentUserAccessor(claims: RequestBearerClaims)`. `.get_current_user() -> CurrentUser`: raises `AuthenticationError("missing bearer token")` if `claims.get()` is `None`, else builds `CurrentUser` via `permissions_for(...)` exactly as `AuthProvider.current_user` does today.

### 5. `di/providers/auth.py` — becomes dumb
```python
class AuthProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def bearer_claims(self, request: Request, tokens: JwtTokenService) -> RequestBearerClaims: ...
    @provide(scope=Scope.REQUEST)
    def current_user_accessor(self, claims: RequestBearerClaims) -> CurrentUserAccessor: ...
    @provide(scope=Scope.REQUEST)
    def current_user(self, accessor: CurrentUserAccessor) -> CurrentUser:
        return accessor.get_current_user()
```

### 6. `infrastructure/current_tenant_accessor.py` (new)
`CurrentTenantAccessor(request: Request, master: MasterSession, settings: Settings, claims: RequestBearerClaims)`, mirroring the C# reference's shape (one class, private helper methods per resolution step):
- `get_current_tenant() -> TenantContext` — today's `TenantDbProvider._resolve` + active/database checks, raising `MissingTenantError`/`TenantNotFoundError`/`AuthorizationError`/`TenantNotActiveError`.
- `get_requested_tenant() -> RequestedTenant` — today's `TenantDbProvider.requested` logic (header-only, non-raising on absence).
- Private helpers: `_resolve_tenant_model`, `_authorize_switch`, `_by_slug_or_id`, `_header_value`. `TENANT_HEADER` constant moves here.

### 7. `di/providers/tenant_db.py` — becomes dumb
Keeps `registry` (engine lifecycle — plain construction, stays as-is) and `engine`/`session` (unchanged — pure construction). `tenant`, `tenant_id`, `requested` become one-line delegations to `CurrentTenantAccessor`, which is itself just constructed (not called) by a new `accessor` provider method. All imports of `application.errors`, `domain.tenancy`, `infrastructure.persistence.master.models`, `sqlalchemy.select`, `JwtTokenService` drop out of this file.

### 8. Use-case constructor typing fixes
- `application/use_cases/token_issuer.py`: `refresh_ttl: timedelta` → `refresh_ttl: RefreshTokenTtl` (import from `application.types`).
- `application/use_cases/invite_user.py`: `invite_ttl: timedelta` → `InviteTtl`, `tenant_id: UUID` → `ResolvedTenantId` (both from `application.types`). Runtime behavior unchanged — `NewType` is identity at runtime.

### 9. `di/providers/config.py` — two trivial derived-value providers
```python
@provide(scope=Scope.APP)
def refresh_token_ttl(self, settings: Settings) -> RefreshTokenTtl:
    return RefreshTokenTtl(timedelta(days=settings.refresh_token_ttl_days))

@provide(scope=Scope.APP)
def invite_ttl(self, settings: Settings) -> InviteTtl:
    return InviteTtl(timedelta(hours=settings.invite_ttl_hours))
```

### 10. `di/providers/use_cases.py` — collapses to `provide_all`
```python
class UseCasesProvider(Provider):
    scope = Scope.REQUEST
    use_cases = provide_all(
        ClaimsFactory, TokenIssuer, Login, RefreshTokens, ChangePassword,
        InviteUser, AcceptInvite, GetMe, ListUsers, ChangeUserRole,
        GetTenantSettings, UpdateTenantSettings,
    )
```
Verified every one of these 12 constructors is already typed entirely in DI-resolvable ports/NewTypes (read all 12 use-case files during exploration) — no other use-case edits needed beyond step 8.

### 11. Split `di/providers/repositories.py`
Delete it; add:
- **`di/providers/master_repositories.py`** — `MasterRepositoriesProvider`: `tenants`, `users`, `app_roles`, `tenant_access`, `refresh_tokens`, `invitations`, `master_uow` (REQUEST scope), `provisioner` (APP scope) — everything keyed on `MasterSession`/`MasterEngine`.
- **`di/providers/tenant_repositories.py`** — `TenantRepositoriesProvider`: `employees`, `tenant_settings`, `tenant_uow` (keyed on `TenantSession`), plus `tenant_scope` (produces `TenantScope`/`SqlTenantScope` — grouped here since its *output* is tenant-workspace access, even though its inputs are `MasterSession` + registry, matching the "reach into tenant data" theme of this module).

### 12. Wire-up updates
`di/providers/__init__.py` and `di/container.py`: replace `RepositoriesProvider` with `MasterRepositoriesProvider` + `TenantRepositoriesProvider`; no other provider list changes (class count for `AuthProvider`/`TenantDbProvider` stays the same, just different bodies).

## Verification
- `uv run ruff check src tests` (from `backend/`) — catches unused imports left behind by the moves (e.g. `application.errors` imports removed from `tenant_db.py`/`auth.py`).
- `uv run pytest` (from `backend/`) — full suite, in particular `tests/di/test_container.py` (asserts container resolution shape, not internal provider structure, so should pass unchanged) and `tests/architecture/test_database_split.py` (guards the master/tenant session split this refactor must not blur).
- Manual spot check: `uv run uvicorn main:app --reload`, hit `/api/v1/auth/login` (exercises `RequestedTenant` + `AuthProvider`-free path) and an authenticated tenant-scoped route (exercises the full `CurrentTenantAccessor.get_current_tenant()` + `CurrentUserAccessor` path) to confirm identical behavior to before the refactor.
