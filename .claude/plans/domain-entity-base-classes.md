# Domain entity base classes (`domain/core/`) + value-object module split

## Context

The domain layer's five entities (`User`, `Tenant`, `Membership`, `Invitation`,
`RefreshTokenRecord`) are flat `@dataclass`es with no shared base. Three problems follow:

1. **Equality is wrong for entities.** A plain `@dataclass` gives field-wise equality, so two
   `User`s with identical attributes compare equal. PRD §7.6 explicitly wants the opposite —
   *"two handsets of the same model are not equal, even with identical attributes, because
   identity is not attributes."* Today nothing enforces that, and `DeviceUnit` (M2) will
   inherit the bug.
2. **Nothing marks which database an entity belongs to.** All five entities are MasterDB
   entities; from M2 the tenant-side entities (`Product`, `DeviceUnit`, `StockMovement`)
   arrive alongside them in `domain/entities/`. With database-per-tenant as the most
   expensive-to-reverse decision in the codebase (CLAUDE.md), "which DB does this live in?"
   should be visible in the type, not inferred from the filename.
3. **`domain/value_objects/money.py` owns two public types** (`Currency` and `Money`).

Outcome: a `domain/core/` package holding a generic entity base and two DB-scope marker
mixins, all five entities migrated onto them, and `Currency` split into its own module.

### Decisions taken during planning

- **No `DomainEvents` list on `Entity`.** PRD line 662 defers domain events (*"Not needed in
  v1... that's the moment to introduce them, and not before"*) and line 835 lists them as
  out-of-scope. Adding the list later is a 3-line change to one base class.
- **No `AuditableEntity` in the domain.** Three grounded reasons:
  - The C# `SetCreated()`/`SetUpdated()` read `DateTime.UtcNow` inside the entity. This
    codebase deliberately routes time through the `Clock` port
    (`backend/src/application/ports/clock.py`) so use cases are testable at any instant.
    A domain base class that reads the wall clock reintroduces exactly what that port removes.
  - PRD §4.3 makes auditability a consequence of the append-only `stock_movements` ledger
    (every row names its author and its cause), not of per-row audit columns. Blanket
    `CreatedBy`/`UpdatedBy` duplicates that with a weaker, mutable version.
  - `UpdatedAt`/`UpdatedBy` are meaningless on the entities that matter most — PRD §4.3:
    *"Movements are never deleted or updated."*

  Where a timestamp *is* business-meaningful it already exists as an explicit field set from
  the `Clock` (`User.created_at`, `Tenant.created_at`, `Invitation.expires_at`,
  `RefreshTokenRecord.revoked_at`) — which is better, because it's deliberate per entity.
  **If blanket audit columns are wanted later** (plausible for the M2 catalog tables), add
  them in `infrastructure/persistence/` as a SQLAlchemy mixin driven by
  `before_insert`/`before_update` event hooks. That is the correct layer: it's a row-history
  concern, not a business rule.
- **`_luhn_checksum` stays inside `imei.py`; `Money`'s arithmetic stays on `Money`.**
  A domain *service* is for behaviour that doesn't belong to any single type — needing
  external data, or spanning several entities. Luhn belongs to exactly one type and needs no
  I/O. Extracting it means `IMEI.__post_init__` calls out to a service, so the value object
  can no longer validate itself — breaking both PRD §4.2 (*"cannot exist in an invalid
  state"*) and CLAUDE.md's rule that a value object which can't self-validate is
  mis-designed. `MoneyService.add(a, b)` is the same mistake with a nicer name (Anemic Domain
  Model). The one thing that would genuinely justify a service here is FX conversion, which
  needs rate data and spans currencies — and PRD line 835 deliberately excludes it from v1.

## Implementation

### 1. New package `backend/src/domain/core/`

**`backend/src/domain/core/entity.py`**

Python has no `I` prefix convention, and `IEntity<TKey>` / `Entity : IEntity<Guid>` can't
both be called `Entity`. Map them as:

- `Entity[TKey]` — the `IEntity<TKey>` equivalent. PEP 695 generic (`requires-python =
  ">=3.14"`, so the native syntax is available), `ABC`, `@dataclass(eq=False, kw_only=True)`,
  declaring `id: TKey`. Defines `__eq__` (same concrete type **and** same `id`) and
  `__hash__` (on `(type(self), self.id)`).
- `UuidEntity(Entity[UUID])` — the `Entity : IEntity<Guid>` equivalent.
  `@dataclass(eq=False, kw_only=True)` with `id: UUID = field(default_factory=uuid4)`.

Two mechanics that must not be missed:

- **`kw_only=True` is required, not stylistic.** `UuidEntity.id` has a default; subclasses add
  fields without defaults, which is a `TypeError` at class-creation time under positional
  dataclass ordering. `kw_only=True` on the base *and every subclass* removes the ordering
  constraint entirely.
- **`eq=False` on every subclass.** A subclass declared `@dataclass(...)` without it
  regenerates a field-wise `__eq__` and silently discards the identity semantics this whole
  change exists to establish.

`Entity` has no abstract members, so `ABC` documents intent without blocking instantiation.
Don't add a dummy abstract method to force it.

**`backend/src/domain/core/markers.py`**

`MasterEntity` and `TenantEntity` — plain empty classes (`__slots__ = ()`), independent of
`Entity`, used as mixins.

> These must **not** be `Protocol`s. An empty `Protocol` is structurally satisfied by every
> object, so `isinstance(anything, MasterEntity)` would return `True` and the marker would
> carry no information. Nominal classes are the only shape that works here.

**`backend/src/domain/core/__init__.py`** — re-export `Entity`, `UuidEntity`,
`MasterEntity`, `TenantEntity`.

### 2. Migrate the five entities in `backend/src/domain/entities/`

Pattern — apply to `user.py`, `tenant.py`, `invitation.py`, `refresh_token.py`:

```python
@dataclass(eq=False, kw_only=True)
class User(UuidEntity, MasterEntity):
    email: str
    ...  # existing fields unchanged; drop the now-inherited `id: UUID`
```

**`membership.py` is the exception.** Its key is composite `(user_id, tenant_id)` — see the
two-column primary key at `backend/src/infrastructure/persistence/master/models.py:47-50`.
It has no `id` and gets no surrogate one (that would mean a PK change and a migration for no
benefit). It takes the marker only:

```python
@dataclass(kw_only=True)
class Membership(MasterEntity):
    user_id: UUID
    tenant_id: UUID
    role: Role
```

Keep its default field-wise equality — with no identity of its own, value equality is the
correct semantics, and `tests/application/fakes.py` keys memberships by the tuple already.

**Two positional call sites break under `kw_only=True`** and must become keyword args:
- `backend/src/application/use_cases/sign_up.py:64`
- `backend/src/application/use_cases/accept_invite.py:78`

Both are `Membership(user.id, tenant.id, Role.OWNER)` → `Membership(user_id=..., tenant_id=...,
role=...)`. Everything else in `src/` and `tests/` already constructs entities with keywords
(verified across `master/repositories.py`, all use cases, `tests/application/builders.py`).

No repository, use case, DTO, or router signature changes — `UuidEntity.id` is the same field
these already read and write.

### 3. Split `Currency` out of `money.py`

- New `backend/src/domain/value_objects/currency.py` — `Currency` (StrEnum), the `_EXPONENTS`
  table, and the module docstring's exponent rationale (UZS=0, USD=2).
- `money.py` keeps `Money` and imports `Currency` from the new module.
- `backend/src/domain/value_objects/__init__.py` — update the import line.

`Currency` is imported *only* through the `domain.value_objects` package `__init__` (confirmed
by grep across `src/` and `tests/`), so this is a one-line change with zero call-site churn.
`imei.py` is left alone.

## Verification

```bash
cd backend
uv run pytest                        # 0 regressions expected; no test asserts whole-entity value equality
uv run ruff check src tests
```

Add `backend/tests/domain/test_entity.py` covering the semantics this change introduces,
since nothing existing exercises them:

- two `User`s with the *same* `id` but different `email` compare **equal**;
- two `User`s with identical fields but different `id` compare **not equal**
  (this is the case that regresses if a subclass forgets `eq=False` — the test is the guard);
- a `User` and a `Tenant` sharing an `id` are **not** equal (type is part of identity);
- entities are usable as `set`/`dict` keys, and mutating a non-id field doesn't move the
  bucket;
- `UuidEntity()` subclasses get a distinct auto `id` when none is passed;
- `isinstance(user, MasterEntity)` is `True`, `isinstance(user, TenantEntity)` is `False`.

Then confirm the stack still boots end-to-end, since `sign_up` and `accept_invite` changed:

```bash
docker compose up -d                 # repo root
cd backend && uv run uvicorn main:app --reload
# POST /api/v1/auth/signup → then GET /api/v1/auth/me with the returned token
```
