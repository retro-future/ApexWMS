# M1 — Tenancy & Auth

> **STATUS (resumed session):** Implementation tasks 1–7 of 9 are **complete and lint-clean** — domain, application, persistence + dual Alembic environments, security/provisioning/CLI, DI wiring, routers, config/deps. `uv run ruff check src` passes and `create_app()` builds 8 routes. **Remaining: tasks 8 and 9 (the test suite).** See the "Remaining work" section at the end — that is the only part left to execute.

## Context

The codebase is at **M0 complete** (skeleton, `/health`, Money/IMEI value objects, Dishka DI, bounded `TenantEngineRegistry`). Nothing of M1 exists yet: no Alembic migrations, no MasterDB tables, no JWT code, no signup/provisioning. The M1 dependencies (`alembic`, `pyjwt`, `argon2-cffi`) are already declared in `backend/pyproject.toml`.

M1 (PRD §10) delivers: MasterDB schema, tenant provisioning, migration fan-out CLI, JWT auth (access + refresh), roles, and the tenant timezone setting (risk table says it must land in M1). **Demo: sign up two tenants; prove tenant A cannot see tenant B.**

Decisions made with the user:
- **Invites return the link in the API response** — no SMTP in M1.
- **Provisioning runs inline in the signup request** — status state machine still exists so failures are retryable; no task queue.

Covers FR-1.1 … FR-1.7 plus the `/settings/tenant` timezone endpoint (minimal: timezone only; letterhead is M7).

## Architecture constraints (from CLAUDE.md / PRD §7.3)

- Flat layout under `backend/src/` — no `apexwms.` prefix, imports like `from infrastructure.config import Settings`.
- Ports (`Protocol`s) live in `application/`, implementations in `infrastructure/`. `application` imports `domain` only — testable with in-memory fakes.
- DI wiring only in `di/providers/` (one module per concern) + `di/container.py`.
- Use `MasterSession`/`TenantSession` NewTypes from `infrastructure/types.py` when wiring providers.
- Replace the `from_context` TenantContext in `TenantDbProvider` with a JWT-derived provider — **do not add a second path** (explicit instruction in CLAUDE.md).

## Implementation plan

### 1. Domain (`backend/src/domain/`)

- `domain/roles.py` — `Role` enum: `OWNER | MANAGER | STOREKEEPER | SELLER`.
- `domain/tenancy.py` — `TenantStatus` enum: `PENDING | PROVISIONING | ACTIVE | FAILED` (PRD §3.2 state machine).
- Add auth-related errors to `domain/errors.py` (e.g. `InvalidCredentialsError`) only where they're genuinely domain rules; HTTP-ish errors (401/403) stay in presentation.

### 2. MasterDB models + Alembic (`backend/src/infrastructure/persistence/`)

SQLAlchemy models (`infrastructure/persistence/master/models.py`), never escaping repositories:

- `tenants` — id (UUID pk), name, status (TenantStatus), created_at.
- `tenant_databases` — tenant_id (fk, unique), db_name, created_at. (db_url is derived from master URL + db_name at runtime — don't store credentials per row.)
- `users` — id (UUID), email (unique), password_hash (nullable until invite accepted), full_name, is_active, created_at.
- `memberships` — user_id + tenant_id (unique pair), role.
- `refresh_tokens` — id (jti UUID), user_id, tenant_id, token_hash (sha256 of the random secret — argon2 unnecessary for high-entropy tokens), expires_at, revoked_at, replaced_by (rotation chain).
- `invitations` — id, tenant_id, email, role, token_hash, expires_at, accepted_at, created_by.

Two Alembic environments (master and tenant schemas diverge permanently):

- `backend/alembic.ini` with two script locations; migrations at `backend/src/infrastructure/persistence/migrations/master/` and `.../migrations/tenant/`.
- Master migration 0001: the six tables above.
- Tenant migration 0001 (minimal M1 schema): `locations` (id, name, is_active) and `tenant_settings` (single row: timezone, default `Asia/Tashkent`). Catalog tables come in M2.

### 3. Migration fan-out CLI (PRD §3.2 mitigation)

`backend/src/infrastructure/cli.py` exposed as a console script `apexwms` in `pyproject.toml` (`[project.scripts]`):

- `apexwms migrate-master` — upgrade MasterDB to head.
- `apexwms migrate --all-tenants` — iterate `tenant_databases`, run `alembic upgrade head` against each, idempotent (Alembic's `alembic_version` table per DB is the version record), continue past failures, and print the fleet's version spread + failures at the end. Partial completion is a reported state, not a crash.

### 4. Auth infrastructure (`backend/src/infrastructure/security/`)

- `password.py` — `Argon2PasswordHasher` (argon2-cffi, argon2id) implementing an application `PasswordHasher` port.
- `jwt.py` — `JwtTokenService`: access token (15 min, claims `sub`=user_id, `tenant_id`, `role`), refresh token = random 256-bit secret + jti, stored hashed in `refresh_tokens`, **rotated on use** (old row gets revoked_at + replaced_by), revocable. Implements a `TokenService` port.

### 5. Provisioning (`backend/src/infrastructure/provisioning.py`)

`TenantProvisioner` (implements an application port), following PRD §3.4 exactly:

1. tenant row already `pending` → set `provisioning`.
2. `CREATE DATABASE apexwms_tenant_<uuid>` on an autocommit connection (Postgres requires it outside a transaction); `IF NOT EXISTS`-style guard for idempotency (catch duplicate_database).
3. Insert/upsert `tenant_databases` row.
4. Run tenant Alembic to head against the new DB (programmatic `alembic.command.upgrade`).
5. Seed: default `Location` "Main Store", `tenant_settings` with timezone (signup accepts timezone, default `Asia/Tashkent`).
6. Set `status = active`; any failure → `status = failed` (a retry re-runs 2–5, all idempotent).

Runs inline during signup.

### 6. Application layer (`backend/src/application/`)

Ports (`application/ports/`): `UserRepository`, `TenantRepository`, `MembershipRepository`, `RefreshTokenRepository`, `InvitationRepository`, `PasswordHasher`, `TokenService`, `TenantProvisioner`, `Clock`, `MasterUnitOfWork`.

Use cases (`application/use_cases/auth/`, one class / one `execute()` each):

- `SignUp` — FR-1.1: create user + tenant (pending) + Owner membership, provision inline, return tokens. Compound input → frozen dataclass command (per §7.3 DTO rule).
- `Login` — FR-1.2/1.3: verify argon2 hash; if the user has multiple memberships and no `tenant_id` in the request, return the tenant list (no tokens); with exactly one membership or an explicit valid `tenant_id`, issue tokens carrying exactly one `tenant_id`.
- `RefreshTokens` — validate + rotate; reuse of a rotated token revokes the whole chain.
- `InviteUser` — FR-1.5: Owner only; create invitation, return the signed single-use link (no email).
- `AcceptInvite` — validate token/expiry/single-use, set password, create membership.
- `ChangeUserRole`, `ListUsers` — Owner endpoints.
- `GetTenantSettings` / `UpdateTenantSettings` — timezone (TenantDB).

Repositories implementing these ports: `infrastructure/persistence/master/repositories.py` (row ↔ domain mapping stays inside).

### 7. DI + request auth (`backend/src/di/providers/`, `backend/src/presentation/`)

- New provider modules: `di/providers/security.py` (APP: hasher, token service), `di/providers/auth.py` (REQUEST: `CurrentUser` from validated bearer token), `di/providers/repositories.py`, `di/providers/use_cases.py`. Re-export from `di/providers/__init__.py`, register in `create_container()` — the established pattern.
- **Replace** `tenant = from_context(...)` in `di/providers/tenant_db.py` with a REQUEST-scope provider: `CurrentUser.tenant_id` → MasterDB lookup of `tenant_databases` (+ assert tenant `active`) → `TenantContext`. Everything downstream (`TenantEngine`, `TenantSession`) is untouched.
- `CurrentUser` = frozen dataclass (user_id, tenant_id, role) extracted from the JWT; unauthenticated requests to protected routes → 401 via a presentation dependency.
- Role enforcement: FastAPI dependency factory `require_role(*roles)` in `presentation/auth.py` → 403 with no side effect (FR-1.6).

### 8. Routers (`backend/src/presentation/routers/`)

Per PRD §8, all under `/api/v1`:

- `auth.py` — `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/accept-invite`, `GET /auth/me`.
- `users.py` — `GET /users`, `POST /users/invite`, `PATCH /users/{id}/role` (Owner).
- `settings.py` — `GET /settings/tenant` (any), `PUT /settings/tenant` (Owner) — timezone only for now.

Pydantic schemas in `presentation/schemas/`; register routers in `presentation/app.py`.

### 9. Config additions (`backend/src/infrastructure/config.py`)

`jwt_secret`, TTLs, `master_db_url` already exist. Add: `invite_ttl_hours` (default 72), `tenant_db_name_prefix` (default `apexwms_tenant_`). Tenant DB URLs derive from `master_db_url`'s host/credentials + the tenant db_name.

## Verification

1. `uv run pytest` — all layers:
   - **Application unit tests** with in-memory fakes (no Postgres): login success/failure, multi-tenant login flow, refresh rotation + reuse-detection, invite accept/expiry/single-use, signup state machine on provisioner failure.
   - **Integration (testcontainers)**: signup provisions a real tenant DB (schema at head, "Main Store" seeded, status `active`); failed provisioning is retryable.
   - **Cross-tenant isolation suite** (`tests/api/test_tenant_isolation.py`) — the M1 demo as a test: sign up tenants A and B, and with A's token hit every tenant-scoped endpoint asserting no B data is reachable; token-for-A with forged/other tenant_id → 401/403 (FR-1.4).
   - **Role matrix tests**: each endpoint × each role → 200/403 per §2.1 (FR-1.6); no side effect on 403.
2. `uv run ruff check src tests`.
3. Manual demo: `docker compose up -d`, `apexwms migrate-master`, `uv run uvicorn main:app --reload`, then via curl/HTTP file: sign up two tenants, log in to each, show `/auth/me` and `/settings/tenant` differ, show A's token cannot touch B.
4. `apexwms migrate --all-tenants` against the two demo tenants — reports both at head; re-run is a no-op (idempotency).

---

# Remaining work: tasks 8 & 9 (the test suite)

## What already exists

- `backend/tests/application/fakes.py` — **written**. In-memory implementations of every port: `FakeClock` (advanceable), `FakeHasher`, `FakeTokenService`, `FakeUserRepository`, `FakeTenantRepository`, `FakeMembershipRepository`, `FakeRefreshTokenRepository`, `FakeInvitationRepository`, `FakeTenantSettingsRepository`, `FakeUnitOfWork` (counts commits), `FakeProvisioner` (flips tenant to ACTIVE, or to FAILED + raises when `fail=True`). Reuse these — do not write new fakes.
- M0 tests that still pass untouched: `tests/domain/test_money.py`, `tests/domain/test_imei.py`.

## Task 8 — application unit tests (no database)

New files under `backend/tests/application/`, each building use cases directly from the fakes:

- `test_sign_up.py` — happy path (user + tenant + Owner membership created, provisioner called with the timezone, tenant ends ACTIVE, tokens returned); duplicate email → `EmailAlreadyRegisteredError`; bad timezone → `InvalidTimezoneError`; `FakeProvisioner(fail=True)` → `ProvisioningFailedError` with the tenant row left FAILED and still present (retryable).
- `test_login.py` — success issues tokens carrying the membership role; wrong password / unknown email / inactive user → `InvalidCredentialsError`; two memberships and no `tenant_id` → `tenant_choices` returned and **no tokens**; explicit `tenant_id` → tokens for exactly that tenant; a tenant the user doesn't belong to → `InvalidCredentialsError` (not a leak); non-ACTIVE tenant → `TenantNotActiveError`.
- `test_refresh_tokens.py` — rotation returns a new pair, revokes the old record and sets `replaced_by`; **reuse of an already-revoked token revokes the whole chain** for that user+tenant and raises `InvalidTokenError`; expired token (via `FakeClock.advance`) rejected; malformed token rejected; role is re-read at rotation.
- `test_invitations.py` — `InviteUser` returns a `"{id}.{secret}"` token and stores only the hash; `AcceptInvite` creates a new user + membership; accepting twice → `InvitationError`; expired → `InvitationError`; existing user gains a second membership; already a member → `AlreadyMemberError`.
- `test_user_management.py` — `ChangeUserRole` updates the role; demoting the **only** Owner → `LastOwnerError`; unknown member → `NotFoundError`; `ListUsers` returns users with roles.
- `test_tenant_settings.py` — get returns the seeded zone; update validates via `application/timezones.py` and commits; invalid zone → `InvalidTimezoneError` and **no commit** (assert `FakeUnitOfWork.commits == 0`).

## Task 9 — integration, isolation, role matrix

**Decision:** testcontainers, with a **session-scoped fixture that skips cleanly when Docker is unavailable** (`pytest.skip("Docker not available")`), so `uv run pytest` stays green on any machine while CI gets full coverage.

- `backend/tests/conftest.py` — session-scoped `postgres_container` fixture (`postgres:16-alpine`, matching `docker-compose.yml`), yielding a `Settings` with `master_db_url` pointed at it and a distinct `jwt_secret`. Runs `migrations.upgrade_sync("master", url)` once (reuse `infrastructure/migrations.py` — do not hand-roll DDL). Provides an `httpx.AsyncClient` over `ASGITransport` bound to `create_app(settings)`, following the existing pattern in `tests/api/test_health.py`. A helper that signs up a tenant and returns its tokens keeps the isolation tests readable.
- `tests/api/test_provisioning.py` — signup drives the tenant to ACTIVE; the tenant database exists, is at Alembic head, and is seeded with `tenant_settings` + the "Main Store" `LocationModel` (constant `DEFAULT_LOCATION_NAME` in `infrastructure/provisioning.py`); re-running `DefaultTenantProvisioner.provision` on the same tenant is idempotent (no duplicate location, still ACTIVE).
- `tests/api/test_tenant_isolation.py` — **the M1 demo as a test (FR-1.4).** Sign up tenants A and B with different timezones; assert `/settings/tenant` returns each tenant's own value under its own token; A's token mutating settings never changes B's; `/users` under A's token lists only A's members; a token whose `tenant_id` claim is swapped to B (re-signed with the real secret) cannot reach B's data because there is no membership; a forged/garbage token → 401.
- `tests/api/test_auth_api.py` — signup → login → refresh → `/auth/me` over HTTP; missing/invalid bearer → 401 with `WWW-Authenticate`; the full invite → accept → login-as-invitee round trip.
- `tests/api/test_role_matrix.py` — for each of the four roles (created via invite+accept), assert the PRD §2.1 matrix on the M1 endpoints: `/users` and `/users/invite` and `PATCH /users/{id}/role` are Owner-only (403 otherwise, **and no side effect** — re-read the list to confirm); `GET /settings/tenant` is any member; `PUT /settings/tenant` is Owner-only.
- **Fix the two M0 tests that M1 changed** (confirmed with the user):
  - `tests/api/test_health.py` — `/health` now reports `master_db` reachability and `live_tenant_engines`; assert `degraded`/`unreachable` without a database, and `ok` when run against the container fixture.
  - `tests/di/test_container.py` — `TenantContext` is no longer `from_context`; its request-scope test must drop `context={TenantContext: ...}`. Keep the no-database checks that still hold (Settings identity, APP-scoped `MasterEngine`, registry caching) and assert the new provider chain resolves `CurrentUser` → `TenantContext`.

## Verification for these two tasks

1. `cd backend && uv run pytest` — unit tests pass with no Docker; integration/isolation/role-matrix tests pass with Docker running and skip cleanly without it.
2. `uv run pytest tests/application` — the pure-application suite, must need no Postgres at all.
3. `uv run ruff check src tests` — clean.
4. Manual demo (needs `docker compose up -d`): `uv run apexwms migrate-master`, `uv run uvicorn main:app --reload`, then sign up two tenants and confirm A's token cannot read B; finish with `uv run apexwms migrate --all-tenants` twice to show the version spread and idempotency.

## Out of scope (later milestones)

Catalog CRUD (M2), ledgers (M3), any business documents, PDF, cost-field omission FR-1.7 enforcement beyond schema design (bites for real in M2+ responses — the response-schema-per-role pattern is established here with `/auth/me` and settings, applied to cost fields when cost-bearing endpoints exist).
