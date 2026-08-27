# Value objects (`domain/value_objects/`)

`Money`, `IMEI`, `CostPool` and `CurrencyTotals` set the pattern for every
value object in the codebase: frozen dataclasses that cannot exist in an invalid state,
validated in `__post_init__` with no I/O. Follow this shape rather than
validating downstream.

- **`Money`** (`money.py`) — integer minor-unit amount + `Currency`. UZS and
  USD have *different* exponents (UZS=0, "so'm" has no minor unit despite
  ISO 4217 nominally saying 2; USD=2, cents) — never assume a shared
  exponent at a call site. Construct from major units only via
  `Money.from_major(str | int | Decimal, currency)` — floats are rejected
  everywhere (`InvalidMoneyError`), because binary floats can't represent
  decimal money exactly and a lost fraction in an inventory system is
  indistinguishable from theft. Arithmetic/comparison across currencies
  raises `CurrencyMismatchError` — there is no implicit conversion.
- **`IMEI`** (`imei.py`) — 15 digits with a valid Luhn check digit,
  validated in `__post_init__` with no I/O. `IMEI.parse()` tolerates
  scanner input (spaces, hyphens). Uniqueness is a database-level concern,
  deliberately not handled here.
- **`CostPool`** (`cost_pool.py`) — weighted-average costing. It is a value
  object, not a service: it depends only on `Money`/`Currency`, never an
  entity. An issue takes a *proportional share* of the pool so a sold-out
  pool lands on exactly zero.
- **`CurrencyTotals`** (`currency_totals.py`) — running totals, one per
  currency, that cannot merge two. The key is always read off the `Money`
  being added and never passed in, which makes §11's highest-risk
  mistake — a `SUM()` that forgot its `GROUP BY currency` — structurally
  impossible rather than merely tested for. Immutable like `CostPool`:
  `add` returns a new instance. Every M8 report and `LedgerReconciler`
  accumulate through it, so there is one implementation of "add money to
  its own column" rather than one per report.
