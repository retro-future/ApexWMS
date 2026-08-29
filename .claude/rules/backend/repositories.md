---
paths:
  - "backend/src/application/commands/**/*.py"
  - "backend/src/application/queries/**/*.py"
---

# One generic repository, reached with a specification

There is one repository implementation for the whole application,
`SqlAlchemyRepository` (`infrastructure/persistence/repositories/base.py`,
narrowed per database in `repositories/tenant.py` and `repositories/master.py`),
reached through one generic DI factory per database. A handler does not get a
per-aggregate repository with named methods; it gets the generic repository
typed to its aggregate and calls `find`/`find_one`/`count`/`exists`/`add`/
`update`/`delete` with a specification. This is the target state from ADR
0007. `Supplier` is the reference for a flat aggregate (read
`application/commands/create_supplier.py`, `update_supplier.py`,
`application/queries/get_supplier.py`, `list_suppliers.py`).
`CreditCompany`, `Customer`, `Location`, `Product` and `Employee` are also
converted and flat; they differ from `Supplier` only in keeping their fast
unit tests (see `specifications.md` rule 7). `Employee` is the one whose
port was also reached through `TenantWorkspace` (`application/ports/tenancy.py`),
now typed `TenantDbRepository[Employee, EmployeeModel]` there too.
`PurchaseOrder` is the reference for one with a line collection that only
changes at creation and re-price (`price_purchase_order_line.py`,
`application/specs/purchase_order.py`). `SupplierReturn` and `WriteOff` are the reference
for one whose lines are added and removed after creation by scanning
(`scan_supplier_return_line.py`, `unscan_supplier_return_line.py`,
`infrastructure/persistence/mappers/supplier_return.py`).
`StockCount` is the reference for two child collections synced at once
(`units` and `lines`). `GoodsReceipt` is the reference for a three-level
aggregate: its lines are fixed at creation and each line's scanned `units`
are synced (`infrastructure/persistence/mappers/goods_receipt.py`), and its
three reads that are not "load a receipt" (`received_quantities`,
`supplier_of`, `origin_of`) moved to `SqlGoodsReceiptQueries` (a query
service, `query-services.md`). `SalesInvoice` is the same as `SupplierReturn`
(lines added and removed by scanning) plus a confirm that writes every
line's price snapshot in one `update`
(`infrastructure/persistence/mappers/sales_invoice.py`); all its projection
reads (the customer account, the debtor list, the total debt, the deviation
report) moved to `SqlSalesInvoiceQueries`, which replaced both the old
`SqlSalesInvoiceRepository` and `SqlSalesReportRepository`. `DeviceUnit`'s
two worklists are `SqlDeviceUnitQueries`; the aggregate itself is the
generic repository. `User`, `Tenant`, `Employee`,
`UserAppRole`, `UserTenantAccess`, `RefreshToken` and `Invitation` are the
MasterDB conversions: they use `MasterDbRepository[E, M]`, wired by
`di/providers/master_repository.py` (the mirror of `tenant_repository.py`),
and their mappers go in the same `COMMON_MAPPERS`.
Read the matching set before converting the next aggregate.

Every aggregate is now on the generic repository. The old `LegacyRepository`
port, the named-method repositories, and the `TenantRepository`/`SqlRepository`
bases are gone. Every projection read is a query service (`query-services.md`).
The only non-generic infra classes left are `SqlTenantSettingsRepository`
(`infrastructure/persistence/tenant/settings.py`, a singleton row) and
`SqlDocumentNumberAllocator` (`tenant/document_number.py`, a locked counter);
both take a bare `TenantSession`. Do not reintroduce a named-method
repository for a new aggregate; use the shape below.

**A ledger or a log** (append-only, PRD §4.3 rule 2) converts the same way
but depends on `TenantAppendOnlyRepository[Entity, Model]`, whose impl
(`SqlAppendOnlyRepository`) is `add` + `get` + the spec reads and has
**no** `update`/`delete` — the rule made structural (`SqlAlchemyRepository`
extends it with the write side). All five are converted:

- `ProductPriceChange` / `DeviceUnitPriceChange` are the reference for a
  log whose `Money` amounts carry no currency of their own (§4.5 rule 3):
  a `viewonly` relationship on the log model (`product`, or
  `device_unit -> product`), the spec `selectinload`s it, the mapper reads
  `model.product.currency`. No projection reads, so no query service.
- `Payment` needs `get` by id (on the port) and one reused spec
  (`PaymentsForInvoice`); its dict/sum reads fold into the one handler.
- `StockMovement` / `FinancialTransaction` are the reference for a ledger
  with real projections: the whole-row reads become specs
  (`MovementsForDocument`, `TransactionsForPair`, ...) and everything that
  returns a `MovementLogRow`, a total or a bare id list moves to a
  `<Ledger>Queries` service (`query-services.md`). A handler that needs
  both takes both — the append-only repo and the queries — as separate
  constructor parameters.

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

3. **A uniqueness check is `exists()` with an inline probe spec, not
   `find_one()` plus a Python id comparison.**

   ```python
   taken = Specification(SupplierModel).where(
       SupplierModel.name == name, SupplierModel.id != supplier.id
   )
   if await self._suppliers.exists(taken):
       raise DuplicateNameError(...)
   ```

   See `specifications.md` rule 3.

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

6. **A plain load by id is `repo.get(id)`, not a `Specification`.** A query
   that only needs "the entity with this id" calls `await repo.get(id)` —
   there is no `XById` spec class for that. `get()` takes no lock and does
   no eager loading, so a command that will mutate the entity still uses the
   `XForWrite` locking spec, and an aggregate whose mapper walks a
   collection still loads through a spec that `selectinload`s it. An
   existence check by id is `await repo.get(id) is not None`.

7. **A write handler whose mapper syncs a child collection passes the write
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
