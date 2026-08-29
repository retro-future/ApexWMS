---
paths:
  - "backend/src/infrastructure/persistence/**/queries/*.py"
  - "backend/src/application/ports/tenant/queries.py"
  - "backend/src/application/ports/master/queries.py"
---

# Query services: reads that return a projection, not a whole aggregate

A `Specification` returns whole entities (`specifications.md` rule 4). A read
that folds joined rows into a `dict`, a DTO or a scalar does not fit one, and
it does not belong on the generic repository. Two homes, by how many places
need it:

- **One handler needs it**: build the `select(...)` and fold its rows in that
  handler. Do not make a class for it.
- **More than one handler needs it**: a `<Aggregate>Queries` class in
  `infrastructure/persistence/<db>/queries/`, behind a `Protocol` port in
  `application/ports/<db>/queries.py`. `SqlGoodsReceiptQueries` is the
  reference (`received_quantities`, `supplier_of`, `origin_of`).

## Rules

1. **A query service takes the session NewType, nothing else.**
   `def __init__(self, session: TenantSession) -> None`. It builds
   `select(...)` against ORM models (importing `sqlalchemy` and
   `infrastructure...models` here is fine, the same allowance
   `application/specs/` has) and returns the finished projection.

2. **It never commits and never mutates.** Reads only. The calling handler
   owns the transaction through the `UnitOfWork`; the query service does not
   take one.

3. **A query service depends on nothing but the session.** No base class,
   no `_page_rows`/`_many_rows` helper — call `session.execute(stmt)` /
   `session.scalar(stmt)` directly, and if a method pages, count and slice
   inline (`SqlSalesInvoiceQueries` and `SqlDeviceUnitQueries` each carry a
   private `_count`).

4. **Do not add a "report repository".** The last two
   (`SqlDeviceUnitReportRepository`, `SqlSalesReportRepository`) are gone —
   their reads live in `SqlDeviceUnitQueries` and `SqlSalesInvoiceQueries`.
   New projection reads are query services.

5. **The DI provider is one hand-written `@provide`** in
   `di/providers/tenant_repositories.py`:
   `def goods_receipt_queries(self, session: TenantSession) -> GoodsReceiptQueries: return SqlGoodsReceiptQueries(session)`.

## The fast unit test

A query service is faked, not spec-driven, so its fake is a plain class that
reads whatever the sibling fake repository holds. `FakeGoodsReceiptQueries`
takes `FakeGoodsReceiptRepository` and folds its aggregates the way the SQL
version folds rows. The `World` exposes it as a property
(`receipt_queries`), built from `world.receipts`.
