# Restructure DI providers into a package + rename `infrastructure/database.py`

## Context

Two small structural refactors requested, plus orientation questions (answered in the chat message accompanying this plan):

1. `di/providers.py` currently holds all three Dishka providers in one module. As milestones add providers (JWT, PDF, repositories, use cases), one file won't scale — split it into a `di/providers/` package with one module per concern.
2. `infrastructure/database.py` contains only `NewType` aliases (`MasterEngine`, `MasterSession`, `TenantEngine`, `TenantSession`) — the name suggests engine/session *implementation* lives there, but it's purely type definitions. Rename to `infrastructure/types.py` (the user's suggestion; safe because it's `infrastructure.types`, a package submodule — it cannot shadow the stdlib `types` module under Python 3's absolute imports).

Note: the working tree still holds the **uncommitted** "flatten src/ layout" refactor from earlier (commit was rejected mid-flow). That must be committed first so this refactor lands as its own clean commit.

## Changes

### 1. Commit the pending flatten refactor (already implemented, tests green)

Everything currently in `git status` (renames from `src/apexwms/*` to `src/*`, new `src/version.py`, pyproject packaging, README/PRD updates, `.gitignore`, `CLAUDE.md`) — commit as:
- `refactor: flatten backend package layout — drop the apexwms wrapper folder`
- `docs: add CLAUDE.md` (separate commit)

### 2. Split `di/providers.py` into a `di/providers/` package

New layout:

```
backend/src/di/
├── __init__.py          # unchanged: re-exports create_container
├── container.py         # create_container — import path unchanged
└── providers/
    ├── __init__.py      # re-exports ConfigProvider, MasterDbProvider, TenantDbProvider
    ├── config.py        # ConfigProvider (Settings via from_context)
    ├── master_db.py     # MasterDbProvider (engine, sessionmaker, session)
    └── tenant_db.py     # TenantDbProvider (registry, engine, session)
```

- `git mv` semantics: delete `di/providers.py`, create the four new modules; each keeps its current code and docstrings (the scope table from the old module docstring moves to `providers/__init__.py`).
- `di/container.py` needs no import change (`from di.providers import ...` still works via the package `__init__.py`).
- Future providers (M1: `auth.py`, `security.py`; M7: `pdf.py`) get their own modules here.

### 3. Rename `infrastructure/database.py` → `infrastructure/types.py`

- `git mv backend/src/infrastructure/database.py backend/src/infrastructure/types.py`
- Update the module docstring's first line ("Database type aliases" stays accurate).
- Update importers:
  - `di/providers/master_db.py`, `di/providers/tenant_db.py` (the new modules)
  - `backend/tests/di/test_container.py`

### 4. Update `CLAUDE.md` references

- Line ~64: `di/providers.py` → `di/providers/` package (one module per concern; add new providers as new modules).
- Line ~84: `infrastructure/database.py` → `infrastructure/types.py`.

### 5. Commit

`refactor: split DI providers into a package; rename infrastructure/database.py to types.py`

## Verification

From `backend/`:
- `uv run pytest` — all 42 tests pass (the DI container tests in `tests/di/test_container.py` exercise the full provider graph).
- `uv run ruff check src tests` — clean.
- `uv run python -c "from main import app; print(app.title)"` — app factory builds the container end-to-end.
- `git status` — clean after commits.
