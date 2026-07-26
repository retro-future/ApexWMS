# Move User + Role into the Tenant DB; reserve MasterDB for SuperAdmins

## Context

ApexWMS is database-per-tenant (PRD §3): MasterDB holds `tenants` + `tenant_databases`, and each tenant owns a physical database with all its business data. M1 shipped auth with **global** `users` and `memberships` in MasterDB — a person is one account that can belong to several tenants, and login resolves the tenant *after* authenticating.

That places tenant-operator identity in the one database that is reachable without a tenant context, which contradicts the isolation promise the architecture is built on: a tenant's staff list, emails, and password hashes sit next to every other tenant's. The intended split is narrower — **MasterDB is the control plane for the Admin portal (SuperAdmins) plus the tenant registry; everything that belongs to a store, including its people, lives in that store's own database.**

Outcome: `users`, their `role`, `invitations`, and `refresh_tokens` move into the tenant schema; MasterDB keeps `tenants`, `tenant_databases`, and new `superadmins` + `superadmin_refresh_tokens`. Both `docs/prd.md` and `CLAUDE.md` are updated to state the new ownership split and to guide future schema decisions (e.g. v2's `SubscriptionPlan` → MasterDB).

### Decisions taken (confirmed with the user)

1. **Tenant-scoped login.** `tenants` gains a unique `slug`. The tenant identifier travels in the request; a person in two tenants has two independent user rows. FR-1.3's "pick a tenant" flow is removed.
2. **`invitations` and `refresh_tokens` follow `User`** into the tenant DB. MasterDB gets its own `superadmin_refresh_tokens`. No cross-database foreign keys anywhere.
3. **`role` is a column on the tenant `users` row**, valued from the existing `domain.roles.Role` StrEnum. `Membership` disappears — inside one tenant DB a user has exactly one role.
4. **Rewrite the `0001` initial migrations in place** (both schemas are still at their untagged initial revision; a `0002` that drops just-created tables is noise). Ship the SuperAdmin table *and* a working admin login so the master side is demoable.

### Two mechanisms this forces (flagging explicitly — they change API contracts)

- **`X-Tenant: <slug>` header on unauthenticated tenant-scoped endpoints** (`/auth/login`, `/auth/refresh`, `/auth/accept-invite`). Dishka resolves `TenantContext` from a *provider*, which cannot cleanly read a request body; a header keeps DI declarative and is the standard multi-tenant convention. Authenticated requests keep resolving the tenant from the JWT — unchanged.
- **`POST /auth/signup` no longer returns tokens.** The owner's `users` row and refresh token now live in a database that does not exist yet when the request starts, so signup returns `{tenant_id, tenant_slug}` with `201`; the client follows with a normal login. Avoids inventing a second, non-ambient tenant-session path just for signup.

---

## Implementation

### 1. Domain (`backend/src/domain/`)

- `entities/user.py` — `User` becomes a `TenantEntity`, gains `role: Role`; drops nothing else.
- `entities/invitation.py`, `entities/refresh_token.py` — swap `MasterEntity` → `TenantEntity`; `RefreshTokenRecord` and `Invitation` drop their `tenant_id` field (the database *is* the tenant — same reasoning as PRD §3.1's "no `tenant_id` column").
- `entities/membership.py` — **delete** (`Membership`, `MembershipKey`).
- `entities/tenant.py` — `Tenant` gains `slug: str`.
- `entities/super_admin.py` — **new** `SuperAdmin(UuidEntity, MasterEntity)`: `email`, `full_name`, `password_hash`, `is_active`, `created_at`.
- `entities/__init__.py` — re-export split: master (`Tenant`, `SuperAdmin`) / tenant (`User`, `Invitation`, `RefreshTokenRecord`).
- `core/markers.py` — update both docstrings to the new split (they currently name users/memberships as master-side).

### 2. Application (`backend/src/application/`)

- `ports/master/repositories.py` — delete `UserRepository`, `MembershipRepository`, `InvitationRepository`, `RefreshTokenRepository`. Keep `TenantRepository`, add `get_by_slug()`. Add `SuperAdminRepository` (`get_by_email`) and `SuperAdminRefreshTokenRepository` (`revoke_all_for_admin`).
- `ports/tenant/repositories.py` — add `TenantUserRepository` (`get_by_email`, `list_all`, `count_owners`), `TenantInvitationRepository`, `TenantRefreshTokenRepository` (`revoke_all_for_user(user_id, now)` — no `tenant_id`), alongside the existing `TenantSettingsRepository`. Reuse the generic `Repository[EntityT, KeyT]` in `ports/repository.py`.
- `ports/provisioning.py` — `provision(tenant_id, timezone, owner: OwnerSeed)`; `OwnerSeed` (email, full_name, password_hash) is a new frozen DTO. Seeding the Owner is now part of PRD §3.4 step 5.
- `dtos.py` — drop `UserWithRole`, `TenantChoice`, and `LoginResult.tenant_choices`; `SignUpCommand` gains `tenant_slug`; `SignUpResult` becomes `{tenant_id, tenant_slug}`; add `AdminLoginResult` / `AdminMeView`.
- Use cases:
  - `login.py` — authenticate against `TenantUserRepository` (tenant already resolved by DI); role comes off the user row. `TenantUnitOfWork` replaces `MasterUnitOfWork`.
  - `sign_up.py` — master-side: slug uniqueness check, create `Tenant`, commit, `provision(..., OwnerSeed)`. No token issuing.
  - `refresh_tokens.py`, `invite_user.py`, `accept_invite.py`, `get_me.py`, `list_users.py`, `change_user_role.py`, `token_issuer.py` — repoint at the tenant repositories/UoW; drop every `tenant_id` argument and `MembershipKey` lookup (`change_user_role` guards last-Owner via `TenantUserRepository.count_owners()`).
  - **New** `admin_login.py`, `get_admin_me.py`, `admin_refresh_tokens.py` — the MasterDB mirror, over `SuperAdminRepository` + `MasterUnitOfWork`.
- `errors.py` — add `TenantNotFoundError` (unknown slug) and `SlugAlreadyTakenError`; `EmailAlreadyRegisteredError` now means "within this tenant".

### 3. Infrastructure (`backend/src/infrastructure/`)

- `persistence/master/models/` — delete `user.py`, `membership.py`, `invitation.py`, `refresh_token.py`; add `super_admin.py`, `superadmin_refresh_token.py`; `tenant.py` gains `slug` (unique index).
- `persistence/tenant/models/` — add `user.py` (with `role`, unique `email` index), `invitation.py`, `refresh_token.py` (no `tenant_id` columns).
- `persistence/master/repositories/` — delete `user.py`, `membership.py`, `invitation.py`, `refresh_token.py`; add `super_admin.py`, `superadmin_refresh_token.py`. Keep using `MasterCrudRepository` (`master/repositories/base.py`).
- `persistence/tenant/repositories/` — add `user.py`, `invitation.py`, `refresh_token.py` on top of the existing `TenantCrudRepository` (`tenant/repositories/base.py`) — these are its first subclasses, exactly as its docstring anticipates.
- `migrations/master/versions/0001_master_initial.py` — rewrite: `tenants` (+`slug` unique), `tenant_databases`, `superadmins`, `superadmin_refresh_tokens`.
- `migrations/tenant/versions/0001_tenant_initial.py` — rewrite: `locations`, `tenant_settings`, `users` (+`role`, unique email), `invitations`, `refresh_tokens`.
- `provisioning.py` — `_seed()` also inserts the Owner `users` row from `OwnerSeed` (idempotent: skip if a user with that email exists), keeping the whole seed in one tenant-DB transaction.
- `security/tokens.py` — add `issue_admin_access(super_admin_id)` / `decode_admin_access()` with a `scope: "admin"` claim and **no** `tenant_id`, so a tenant token can never satisfy an admin route or vice versa. `AdminClaims` alongside `AccessClaims`.
- `types.py`, `tenancy.py` — docstrings only (they describe master as holding users/memberships).
- `cli.py` — add `apexwms create-superadmin --email --full-name [--password]`; there is no signup path for SuperAdmins, so bootstrap has to live here.

### 4. DI (`backend/src/di/providers/`)

- `tenant_db.py` — split `TenantContext` resolution into a request-scoped **`TenantRef`** that reads the `X-Tenant` slug header first and falls back to the JWT's `tenant_id`, raising `TenantNotFoundError` if neither is present. `TenantContext` then does the MasterDB `tenants`/`tenant_databases` lookup (by slug or id) and the ACTIVE check exactly as today. Critically, `TenantContext` must **no longer depend on `CurrentUser`**, or the login path 401s before it can authenticate.
- `auth.py` — keep `CurrentUser`; add a request-scoped `CurrentSuperAdmin` from `decode_admin_access`.
- `repositories.py` — master side keeps `TenantRepository` + the two superadmin repos; tenant side gains users/invitations/refresh-tokens.
- `use_cases.py` — rewire constructors; add the three admin use cases.
- `container.py` / `providers/__init__.py` — unchanged in shape; only if a new provider module is added.

### 5. Presentation (`backend/src/presentation/`)

- `schemas/auth.py` — `SignUpRequest` gains `tenant_slug`; `SignUpResponse` → `{tenant_id, tenant_slug}` (no tokens); `LoginRequest`/`LoginResponse` drop `tenant_id`/`tenants`; delete `TenantChoiceResponse`.
- `schemas/users.py` — `UserResponse.from_entity(user)` instead of `from_entry(UserWithRole)`.
- `routers/auth.py` — unchanged routes; login/refresh/accept-invite now implicitly tenant-scoped via the header.
- `routers/users.py` — drop the `current.tenant_id` arguments now that the session *is* the tenant.
- `routers/admin.py` — **new**: `POST /admin/auth/login`, `POST /admin/auth/refresh`, `GET /admin/auth/me`; `schemas/admin.py` alongside. Register in `app.py`.
- `errors.py` — map the new application errors to 404/409.

### 6. Tests (`backend/tests/`)

- `application/fakes.py`, `application/builders.py` — drop `FakeMembershipRepository`, add `FakeTenantUserRepository` (role on the user) and superadmin fakes; `FakeProvisioner.provision` takes `OwnerSeed`.
- `application/test_login.py`, `test_sign_up.py`, `test_invitations.py`, `test_user_management.py`, `test_refresh_tokens.py` — drop the tenant-selection cases, assert role off the user row; add a test that signup seeds the Owner into the tenant DB.
- `conftest.py` — the `TRUNCATE` in `clean_master` becomes `superadmin_refresh_tokens, superadmins, tenant_databases, tenants`; the `sign_up` fixture sends a slug and then logs in with `X-Tenant` to obtain tokens.
- `api/test_auth_api.py`, `test_role_matrix.py`, `test_tenant_isolation.py`, `test_provisioning.py`, `di/test_container.py` — update accordingly. **The isolation suite gains the case that matters most here:** two tenants with the *same* owner email are two unrelated accounts, and tenant A's token reaches no row of tenant B's `users`.

### 7. Documentation

**`docs/prd.md`**
- §3.1 — rewrite the model: MasterDB = `tenants`, `tenant_databases`, `superadmins` (Admin portal only); TenantDB = users, roles, invitations, refresh tokens, and all business data. State plainly that no tenant-operator identity exists in MasterDB.
- §3.3 — request lifecycle gains the unauthenticated branch (`X-Tenant` slug → tenant registry → engine) next to the JWT branch.
- §3.4 — provisioning step 5 seeds the Owner **user row** (not a membership).
- §5.1 — FR-1.1 (signup returns tenant + slug, client then logs in), FR-1.2 (login is tenant-scoped), **FR-1.3 replaced**: one account per tenant; the same email in two tenants is two accounts. FR-1.5 invitations are tenant-local.
- §7.5 — scope table: MasterDB session/`SuperAdmin` at APP/REQUEST vs the tenant session.
- §8 — add the `/admin/auth/*` table; note `X-Tenant` on the anonymous auth routes.
- **New "Future / v2" subsection** (as §3.5, adjacent to the ownership split it constrains): records that **`SubscriptionPlan` will be added to the MasterDB in v2** — billing is a property of the tenant-as-customer, held by the control plane, never inside a tenant's own database. Cross-reference it from the §11 "Deferred to v2" list.

**`CLAUDE.md`** — new **"Infrastructure architecture: MasterDB vs TenantDB"** section under Architecture, covering: what each database owns (Master → `tenants`, `tenant_databases`, SuperAdmin/Admin-portal auth; Tenant → Users, Roles, and all business data); why operator identity moved out of Master; the two tenant-resolution paths (JWT vs `X-Tenant`); and **the rule for future schema decisions** — *does this row describe a tenant to the platform, or describe the platform's own operators? Then MasterDB. Everything else is tenant-side.* — with v2's `SubscriptionPlan` given as the worked example (MasterDB). Also correct the existing multi-tenancy bullets that still say "global `users`, `memberships`".

---

## Verification

```bash
docker compose up -d                        # repo root
cd backend
uv run ruff check src tests
uv run pytest                               # domain + application suites need no Docker
uv run pytest tests/api                     # integration: testcontainers Postgres
```

End-to-end by hand (`uv run uvicorn main:app --reload`):

1. `POST /api/v1/auth/signup` with `tenant_slug=acme` → `201 {tenant_id, tenant_slug}`; confirm `apexwms_tenant_<uuid>` contains a `users` row with `role=owner`, and MasterDB's `users` table **does not exist**.
2. `POST /api/v1/auth/login` with `X-Tenant: acme` → tokens; `GET /auth/me` with the bearer token returns the Owner.
3. Sign up a second tenant `beta` **with the same owner email** — it succeeds and is a separate account; tenant A's token returns no data from tenant B (covered by `tests/api/test_tenant_isolation.py`).
4. `POST /users/invite` → `POST /auth/accept-invite` with `X-Tenant: acme` → login as the invitee; `PATCH /users/{id}/role` still refuses to demote the last Owner.
5. `uv run apexwms create-superadmin --email admin@apexwms.uz` → `POST /api/v1/admin/auth/login` → `GET /admin/auth/me`. Assert a tenant access token is rejected by `/admin/auth/me` and an admin token is rejected by `/auth/me`.
6. `uv run apexwms migrate --all-tenants` reports every tenant at head.
