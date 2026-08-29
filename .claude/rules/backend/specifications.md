---
paths:
  - "backend/src/application/specs/**/*.py"
---

# Specifications: the reads worth a name

A specification is a query object for the one generic repository
(`SqlAlchemyRepository`). A class lives in `application/specs/<aggregate>.py`
and is re-exported from `application/specs/__init__.py`. There is never a
new repository class or a new method on a Protocol.

Most reads are **not** classes:

- A plain load by id is `await repo.get(id)` (see `repositories.md` rule 6).
- A one-off equality probe is built inline in the handler:
  `Specification(SupplierModel).where(SupplierModel.name == name)`, passed
  to `exists()` / `find_one()` / `find()`.

A class is for a query that is genuinely more than that: a `.lock()`ing
write spec, one that eager-loads a collection, or a browse spec with
`ilike` / `or_` / several optional filters and an ordering.
`application/specs/supplier.py` is the reference for a flat aggregate;
`purchase_order.py` for eager-loaded lines; `supplier_return.py` for a
chained `selectinload` on a nullable relationship. Mapper rules: `mappers.md`.
Handler-side rules: `repositories.md`.

## Rules

1. **A specification is written against the ORM model, never the domain
   entity** (`SupplierModel.name == name`, not `Supplier.name == name`).
   Importing SQLAlchemy and ORM models into `application/` is intentional
   (ADR 0007), not something to "fix" in review. This holds for an inline
   `Specification(...).where(...)` in a handler too.

2. **The read/write distinction is `repo.get()` vs `XForWrite`.** A query
   that only displays an entity loads it with `await repo.get(id)` — no
   lock, no class. A command that loads an entity to mutate it uses the
   aggregate's `XForWrite` class, which `.lock()`s (and eager-loads a
   collection when the mapper needs one). Using a plain read where a write
   path needs the lock reopens the race the lock exists to close.

3. **A uniqueness probe is inline `Specification` + `exists()`, not
   `find_one()` plus a Python comparison.**

   ```python
   taken = Specification(SupplierModel).where(
       SupplierModel.name == name, SupplierModel.id != supplier.id
   )
   if await self._suppliers.exists(taken):
       raise DuplicateNameError(...)
   ```

   The "not itself" clause is `Model.id != entity.id`; the surrounding
   `XForWrite` load already holds the row lock that makes the check safe.

4. **No new `Specification` fields.** No `columns`, `group_by`, `having`,
   or `select_from`. A specification returns whole entities. A read that
   returns a projection (an `AgeingRow`, a `dict[UUID, int]`, a bare `UUID`)
   goes in a query service (`query-services.md`), or the one handler that
   needs it, not a `Specification`.

5. **The fluent methods mutate and return `self`.** `.page()`, `.where()`,
   `.order()` change the spec in place. A handler must count first, then
   page the same object (see `repositories.md` rule 4).

6. **When to write a class vs inline.** Inline when the whole query is
   equality / `IN` criteria and optionally an `.order()` — even when two or
   three handlers do the same one (`Specification(UserModel).where(
   UserModel.email == email)` is short enough to repeat). Write a class
   when it `.lock()`s, when it eager-loads, or when it needs `ilike` /
   `or_` / a stack of optional filters (every `XBrowse`). `StockLevelForPair`
   is the one borderline class kept on reuse alone: every posting service
   does that exact pair lookup.

7. **The in-memory fake evaluates inline equality specs directly.**
   `tests/application/fakes.py`'s `_spec_matches` walks `spec.criteria` for
   `==` / `!=` / `IN` over a plain column, so an inline probe needs nothing
   extra to work against a fake. A **browse** spec still stores its filters
   as plain attributes (`self.search`, `self.is_active`) because the fake
   evaluates those by hand, not through `_spec_matches` — `ilike` and `or_`
   are not something the fake parses. A spec whose value is an enum stored
   as a string or a value object (`ProductBySku`, `DeviceUnitByImei`,
   `ActiveOwners`) stays a class for the same reason: `_spec_matches` would
   compare the raw column value to the entity's typed attribute and miss.
