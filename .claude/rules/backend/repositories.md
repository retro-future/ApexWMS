---
paths:
  - "backend/src/application/commands/**/*.py"
  - "backend/src/application/queries/**/*.py"
---

# One generic repository, reached with a specification

There is one repository implementation for the whole application,
`SqlAlchemyRepository` (`infrastructure/persistence/repository.py`), reached
through one generic DI factory per database. A handler does not get a
per-aggregate repository with named methods; it gets the generic repository
typed to its aggregate and calls `find`/`find_one`/`count`/`exists`/`add`/
`update`/`delete` with a specification. This is the target state from ADR
0007. `Supplier` is the reference for a flat aggregate (read
`application/commands/create_supplier.py`, `update_supplier.py`,
`application/queries/get_supplier.py`, `list_suppliers.py`);
`PurchaseOrder` is the reference for one with a line collection that only
changes at creation and re-price (`price_purchase_order_line.py`,
`application/specs/purchase_order.py`). `SupplierReturn` is the reference
for one whose lines are added and removed after creation by scanning
(`scan_supplier_return_line.py`, `unscan_supplier_return_line.py`,
`infrastructure/persistence/mappers/supplier_return.py`). Read the matching
set before converting the next aggregate.

Aggregates not yet converted keep their old named-method repository under
`infrastructure/persistence/tenant/repositories/`, keyed by a
`LegacyRepository[Entity, KeyT]` Protocol in
`application/ports/tenant/repositories.py`. Do not extend that pattern for a
new aggregate; convert it to the shape below.

Mapper rules: `mappers.md`. Specification rules: `specifications.md`. DI:
`repository-providers.md`.

## Rules

1. **Depend on `TenantDbRepository[Entity, Model]` /
   `MasterDbRepository[Entity, Model]`, never the bare `Repository[Entity,
   Model]`.** The bare port has no DI factory; it exists only so both
   database-specific ports share one method set. Depending on it directly
   surfaces as `NoFactoryError` at resolution, not at `ty check`.

   ```python
   def __init__(
       self,
       suppliers: TenantDbRepository[Supplier, SupplierModel],
       clock: Clock,
       uow: TenantUnitOfWork,
   ) -> None: ...
   ```

2. **A command that loads an entity to mutate it uses the locking spec.**

   ```python
   supplier = await self._suppliers.find_one(SupplierForWrite(request.supplier_id))
   ```

   A query that only displays the entity uses the plain spec. See
   `specifications.md` rule 2.

3. **A uniqueness check is `exists()` with a probe spec, not `find_one()`
   plus a Python id comparison.**

   ```python
   if await self._suppliers.exists(SupplierNameTakenByAnother(name, supplier.id)):
       raise DuplicateNameError(...)
   ```

4. **`count()` and the paged `find()` take the same specification object,
   counted first.** The fluent methods mutate and return `self`, so:

   ```python
   spec = SupplierBrowse(search=request.search, is_active=request.is_active)
   total = await self._suppliers.count(spec)
   suppliers = await self._suppliers.find(spec.page(request.page, request.page_size))
   ```

   `count()` ignores `limit`/`offset`/`order_by` on its own, but the two
   calls still have to share one spec, or a filter can be applied to the rows
   and forgotten on the total.

5. **Repositories exist only for aggregate roots.** Wanting to fetch a child
   entity by its own id is a sign the aggregate boundary is wrong, not a
   missing repository.

6. **A write handler whose mapper syncs a child collection passes the write
   spec to `update()`.** `update(entity)` alone re-fetches with
   `session.get()`, which does not eager-load, and the model loaded by
   `find_one` is usually already gone from the session's weak identity map,
   so a collection the mapper reads comes back unloaded. Reuse the one spec:

   ```python
   spec = PurchaseOrderForWrite(request.purchase_order_id)
   order = await self._orders.find_one(spec)
   ...
   await self._orders.update(order, spec)
   ```

   Every `SupplierReturn` write handler does this, including `confirm` and
   `cancel`, which do not touch lines themselves but go through a mapper
   that syncs them. A flat aggregate (`Supplier`) whose mapper touches only
   scalar columns still calls the bare `update(entity)`.

## Known limits, current as of the Supplier conversion

- The entity/model pairing in `MapperRegistry` is a runtime dict lookup, not
  something `ty` checks. `TenantDbRepository[Location, SupplierModel]` would
  resolve and hand back a `SupplierMapper`; only a truly unmapped model fails
  (`UnmappedModelError`).
- `SqlUnitOfWork` has no `__aenter__`/`__aexit__` yet. Handlers call
  `await self._uow.commit()` explicitly, not `async with self._uow`.
  Converting to a context manager is a separate cross-cutting change; do not
  do it while converting one aggregate.
