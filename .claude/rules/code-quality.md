---
paths:
  - "**/*"
---

# Code Quality (all source code)

## Single Responsibility

- Split a file when it has more than one clear responsibility, not just because it crossed a line count.
- Line counts are a smell, not a verdict. Cohesive long files are fine; tangled short ones aren't.
- This is the general form of the CQRS-specific rule in `.claude/rules/backend/handler-helpers.md`: a command/query module owns one operation, nothing else.

## Lines of Code (soft targets / refactor thresholds)

| File type                                                     | Aim     | Refactor at |
| -------------------------------------------------------------- | ------- | ----------- |
| Python CQRS command/query handler (`commands\|queries/*.py`)   | 50–120  | 150+        |
| Python domain entity (`domain/entities/*.py`)                  | 100–200 | 300+        |
| Python domain service (`domain/services/*.py`)                 | 100–200 | 300+        |
| Python application service (`application/services/*.py`)       | 150–300 | 400+        |
| Python repository (`infrastructure/persistence/**/repositories/*.py`) | 150–300 | 400+  |
| Python router (`presentation/routers/*.py`)                    | 100–250 | 350+        |
| React/Next component (`.tsx`)                                  | 150–250 | 300–400     |
| React hook (`use*.ts`)                                         | 50–150  | 200+        |
| Frontend `lib/*.ts` helper module                               | 100–250 | 350+        |

Generated files (Alembic migrations, OpenAPI-generated clients, `frontend/messages/*.json`) — **ignore these rules**.

## How to Split

- **Large Python CQRS handler**: this almost always means a private helper or data-loading logic snuck in. Follow `.claude/rules/backend/handler-helpers.md` — logic shared across handlers moves to a DI-injected class in `application/services/`, logic used by exactly one handler stays a private method on that handler class, and either way the handler itself stays thin.
- **Large domain entity or domain service**: extract a value object (`domain/value_objects/`) for a self-validating piece of state, or split a second responsibility into its own domain service. Domain code has zero I/O, so a growing file there is usually mixed concerns, not mixed layers.
- **Large application service**: split along workflow seams (e.g. `removal_posting.py` vs `removal_scanning.py` for the two things a removal document needs), not arbitrary line counts.
- **Large repository**: move a read-only joined query into a dedicated query service (see `SqlSalesInvoiceQueries.list_deviations`) rather than growing every CRUD method in place.
- **Large router**: routers should be thin dispatch to handlers via the mediator; a router growing past its budget usually means response shaping or validation leaked in that belongs in a `models/` response class or the handler itself.
- **Large React page/detail component**: extract subcomponents (e.g. `SurplusWorklist` off the stock count screen), push data fetching and derived state into a custom hook, split repeated row/detail blocks into their own component.
- **Large `lib/*.ts` helper module**: split along the same workflow seams as a Python application service, one file per concern (e.g. `stock-counts.ts` for step logic vs. a separate module for API calls).
