# Clean Architecture — the dependency rule (PRD §7.3)

```
presentation ──▶ application ──▶ domain
      │                │             ▲
      └───▶ infrastructure ──────────┘
                (implements ports defined in application)
```

## Layout is flat under `src/`, not `src/apexwms/`

`backend/src/` has no wrapping package — `domain/`, `application/`,
`infrastructure/`, `presentation/`, `di/`, `main.py`, and `version.py` sit
directly under `src/` and import as top-level modules
(`from infrastructure.config import Settings`, not
`from apexwms.infrastructure.config import Settings`). This is deliberate;
do not reintroduce an `apexwms/` wrapper or `apexwms.`-prefixed imports.

This works because `backend/pyproject.toml` declares each subpackage
explicitly for Hatchling and strips the `src/` prefix:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/domain", "src/application", "src/infrastructure", "src/presentation", "src/di"]
include = ["src/main.py", "src/version.py"]
sources = ["src"]
```

Adding a new top-level package under `src/` (e.g. a future `worker/`) means
adding it to `packages` here too, or it won't ship.

## What each layer owns

- **`domain/`** — pure Python entities and value objects (`Money`, `IMEI`),
  domain errors. **Zero imports from outside `domain/`** — no SQLAlchemy, no
  FastAPI, no Pydantic. If a value object can't validate itself without a
  database, the design is wrong.
- **`application/`** — CQRS: a `Command`/`Query` (one Pydantic message, one
  `IRequestHandler`, one business operation — `LoginCommand`/`LoginHandler`)
  and the **ports** a handler needs, as `Protocol`s (`UserRepository`,
  `UnitOfWork`, `Clock`, ...). `application/core/` holds the shared CQRS
  primitives (`IRequest`, `IRequestHandler`, `Command`, `Query`,
  `Result`/`ResultWithData`/`PagedResult`) — see `docs/prd.md` §7.3 for the
  full pattern and the DI-context-vs-CQRS-message DTO split.
  `application/commands/` and `application/queries/` hold one file per
  operation and nothing else
  (`.claude/rules/backend/handler-helpers.md`); `application/models/` holds
  each operation's *response* payload class instead
  (`.claude/rules/backend/cqrs-response-models.md`) — not to be confused
  with `application/dtos/`, which holds frozen DI-context dataclasses that
  never reach an HTTP wire; `application/services/` holds collaborator
  services composed inside a handler but never invoked directly from a
  route (`ClaimsFactory`, `TokenIssuer`). Depends on `domain` for business
  rules, and on `pydantic` for its message layer — `domain` stays
  framework-free.
- **`infrastructure/`** — implementations of those ports: SQLAlchemy
  repositories, the tenant engine registry, JWT, PDF rendering.
  `application` never imports from here — the port lives in `application`,
  the implementation lives here, satisfying it (dependency inversion).
- **`presentation/`** — FastAPI routers, exception handlers. Thin: a
  route's request body **is** a `Command`/`Query` from `application` — no
  separate presentation-layer request/response schema. A router authorizes,
  calls the paired handler via `FromDishka[...]`, and returns what it
  returns (a `Result`/`ResultWithData[...]`, already a Pydantic model).
  Does **not** contain DI wiring.
- **`di/`** — the composition root. The only package allowed to import from
  every other layer. `di/providers/` holds Dishka `Provider`s, one module
  per concern (`config.py`, `master_db.py`, `tenant_db.py`, `handlers.py`);
  `di/container.py`'s `create_container()` assembles them. As milestones
  add dependencies, add a new module under `di/providers/`, re-export it
  from its `__init__.py`, and register it in `create_container()` — don't
  scatter container-building code elsewhere.

**Why ports live in `application`, not `infrastructure`:** a handler
declares what it needs; infrastructure satisfies it. This lets
`application` be tested with in-memory fakes and no database at all — keep
it that way.
