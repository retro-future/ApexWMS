---
paths:
  - "backend/src/application/specs/**/*.py"
---

# Specifications: one class per read or write-lock

A specification is the query for the one generic repository
(`SqlAlchemyRepository`). One class per distinct read or write-lock the use
cases need, in `application/specs/<aggregate>.py`, re-exported from
`application/specs/__init__.py`. There is never a new repository class or a
new method on a Protocol. `application/specs/supplier.py` is the reference
for a flat aggregate; `application/specs/purchase_order.py` for one whose
specs eager-load a line collection; `application/specs/supplier_return.py`
for one that chains a second `selectinload` per line for a nullable
relationship (the scanned handset). Mapper rules live in `mappers.md`; how
handlers call these in `repositories.md`.

## Rules

1. **A specification is written against the ORM model, never the domain
   entity** (`SupplierModel.name == name`, not `Supplier.name == name`).
   Importing SQLAlchemy and ORM models into `application/` is intentional
   (ADR 0007), not something to "fix" in review.

2. **Read specs and write specs are different classes even when their
   `where()` is identical.** `SupplierById` has no lock; `SupplierForWrite`
   does. A command that loads an entity to mutate it uses the locking spec; a
   query that only displays the entity uses the plain one. Reusing the
   locking spec for a read-only path takes a row lock nothing needs; reusing
   the plain one for a write path reopens the race the lock exists to close.

3. **A uniqueness probe is a spec used with `exists()`, not `find_one()` plus
   a Python comparison.**

   ```python
   class SupplierNameTakenByAnother(Specification[SupplierModel]):
       def __init__(self, name: str, supplier_id: UUID) -> None:
           super().__init__(SupplierModel)
           self.where(SupplierModel.name == name, SupplierModel.id != supplier_id)
   ```

4. **No new `Specification` fields unless you are also editing this file to
   say so.** No `columns`, `group_by`, `having`, or `select_from`. A
   specification returns whole entities. A projection or an aggregate query
   belongs in a query service (not yet built), never in a bigger
   `Specification`.

5. **The fluent methods mutate and return `self`.** `.page()`, `.where()` and
   the rest change the spec in place. A handler must count first, then page
   the same object (see `repositories.md` rule 4).
