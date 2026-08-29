---
paths:
  - "backend/src/infrastructure/persistence/mappers/**/*.py"
---

# Per-aggregate mappers for the one generic repository

The application has one repository implementation, `SqlAlchemyRepository`
(`infrastructure/persistence/repositories/`), reached through one generic DI
factory per database. What varies per aggregate is a **mapper** (entity ↔ ORM
row) and a **specification** (the query), never a new repository class. This
is the target state from ADR 0007. `Supplier` is the reference conversion:
read `infrastructure/persistence/mappers/supplier.py` before writing a new
mapper. Specification rules live in `specifications.md`; handler and DI rules
in `repositories.md` and `repository-providers.md`.

## Where a mapper lives

One class per aggregate root in
`infrastructure/persistence/mappers/<aggregate>.py`, registered as an
instance in that package's `__init__.py` `COMMON_MAPPERS` list. Adding the
instance to `COMMON_MAPPERS` is the whole wiring step.

**A flat aggregate whose entity fields and ORM columns share names and need
no conversion gets no file of its own.** It is registered directly in
`COMMON_MAPPERS` as `AutoMapper(CreditCompany, CreditCompanyModel)` —
`AutoMapper` (`mappers/auto.py`) copies field-for-field by name off the
entity's `dataclasses.fields()`. `CreditCompany` and `Customer` are the
references. Write a hand mapper the moment the aggregate has a value object
(`Money`, `IMEI`), an enum stored under a different representation, a
column with no matching field, or a child collection.

## Rules

1. **`to_model` takes an optional second argument and mutates it when given
   one.**

   ```python
   def to_model(self, entity: Supplier, model: SupplierModel | None = None) -> SupplierModel:
       model = model or SupplierModel(id=entity.id)
       model.name = entity.name
       ...
       return model
   ```

   `update()` on the generic repository loads the persistent row and passes
   it in; mutating it in place is what lets SQLAlchemy's change tracking emit
   the `UPDATE`. Returning a fresh instance instead produces a duplicate
   `INSERT`.

2. **A mapper declares `model: type[TModel]` naming its own table.** The
   generic factory is handed `type[M]` and nothing else, so `MapperRegistry`
   finds the mapper from the bare model class. The type checker cannot see a
   missing or duplicated `model`: `MapperRegistry` raises `UnmappedModelError`
   for the missing case, and silently picks whichever mapper registered last
   for a duplicate.

3. **One mapper class per aggregate root. Never one for a child entity.**
   `GoodsReceiptLine`/`ReceivedUnit` are mapped by private methods
   (`_line_to_entity`, `_line_to_model`, ...) on `GoodsReceiptMapper`. Wanting
   to fetch a child by its own id is a sign the aggregate boundary is wrong,
   not a missing mapper.

4. **`domain/` does not change for this.** No imperative mapping, no logic
   pulled out of an entity into a service. If a mapper needs data a domain
   method doesn't expose, add the accessor to the entity; the mapper still
   does the translating.

## A multi-entity aggregate: one root mapper, private child methods

When the aggregate has child entities, the single mapper class walks the
whole tree. `to_entity`/`to_model` handle the root and delegate each child
level to a private `_line_to_entity`/`_unit_to_model`-style method. No child
gets its own mapper class, its own `model` attribute, or its own registry
entry.

```python
class GoodsReceiptMapper:
    model = GoodsReceiptModel

    def to_entity(self, model: GoodsReceiptModel) -> GoodsReceipt:
        return GoodsReceipt(
            id=model.id,
            tenant_id=model.tenant_id,
            number=model.number,
            status=model.status,
            acquisition_source=model.acquisition_source,
            supplier_id=model.supplier_id,
            location_id=model.location_id,
            created_by=model.created_by,
            created_at=model.created_at,
            confirmed_by=model.confirmed_by,
            confirmed_at=model.confirmed_at,
            lines=[self._line_to_entity(line) for line in model.lines],
        )

    def _line_to_entity(self, model: GoodsReceiptLineModel) -> GoodsReceiptLine:
        return GoodsReceiptLine(
            id=model.id,
            product_id=model.product_id,
            quantity=model.quantity,
            is_serial=model.is_serial,
            units=[self._unit_to_entity(u) for u in model.units],
        )

    def _unit_to_entity(self, model: ReceivedUnitModel) -> ReceivedUnit:
        return ReceivedUnit(id=model.id, imei=IMEI(model.imei))

    def to_model(
        self, entity: GoodsReceipt, model: GoodsReceiptModel | None = None
    ) -> GoodsReceiptModel:
        model = model or GoodsReceiptModel(id=entity.id)
        model.tenant_id = entity.tenant_id
        model.number = entity.number
        model.status = entity.status
        model.confirmed_by = entity.confirmed_by
        model.confirmed_at = entity.confirmed_at
        # ... remaining scalar fields ...
        if not model.lines:  # children are written once, at creation
            model.lines = [self._line_to_model(line) for line in entity.lines]
        return model

    def _line_to_model(self, entity: GoodsReceiptLine) -> GoodsReceiptLineModel:
        return GoodsReceiptLineModel(
            id=entity.id,
            product_id=entity.product_id,
            quantity=entity.quantity,
            is_serial=entity.is_serial,
            units=[self._unit_to_model(u) for u in entity.units],
        )

    def _unit_to_model(self, entity: ReceivedUnit) -> ReceivedUnitModel:
        return ReceivedUnitModel(id=entity.id, imei=str(entity.imei))
```

Notes on this shape:

- `to_entity` reads `model.lines` and `line.units` directly, so those
  relationships must be eager-loaded by the specification. Declare them
  `lazy="raise"` (see the known limit below) so a spec that forgets fails at
  the query, not inside a domain method.
- A create-only aggregate builds `model.lines` on the fresh path and leaves
  it alone otherwise. An aggregate whose lines change after creation syncs
  the collection instead (next section).

## Syncing a child collection that changes after creation

`PurchaseOrder` only ever re-prices an existing line, so its `to_model`
update path matches lines by id and copies one scalar. `SupplierReturn`
adds and removes lines by scanning while the return is a draft, so its
mapper does a full id-keyed sync: with `cascade="all, delete-orphan"` on
the relationship, dropping a row from `model.lines` issues the `DELETE` and
appending a new child issues the `INSERT`.

```python
def _sync_lines(self, entity: SupplierReturn, model: SupplierReturnModel) -> None:
    want = {line.id: line for line in entity.lines}
    for row in list(model.lines):
        line = want.get(row.id)
        if line is None:
            model.lines.remove(row)          # delete-orphan issues the DELETE
        else:
            row.quantity = line.quantity
    have = {row.id for row in model.lines}
    for line in entity.lines:
        if line.id not in have:
            model.lines.append(self._line_to_model(line))
```

The scan/unscan handlers then hold no `add_line`/`remove_line` port method:
they mutate `document.lines` on the aggregate and call
`returns.update(document, spec)`. `SupplierReturn` and `WriteOff` are the
reference. Cost: one `find_one` plus one spec re-load per beep (§6's 200ms
still holds on a local database); do not reach for a repository method per
child row to avoid it.

`StockCount` has **two** child collections (`units` and `lines`), each with
its own `_sync_*` method called from `to_model`. The unit sync copies four
mutable scalars onto a matched row (a scan sets `scanned`, and later
`product_id`/`acquisition_cost_minor` for a surprise); the line sync copies
only `counted_quantity`. A surprise unit's `product` relationship is
nullable, so `_unit_to_entity` reads the currency only
`if model.product is not None`.

`GoodsReceipt` is **three** levels (receipt to lines to scanned units) and
they change at different times: the lines are fixed when the receipt opens,
each line's `units` are scanned, priced and unscanned while it is a draft.
So `to_model`'s update path has one `_sync_units` that matches `model.lines`
to `entity.lines` by id and never inserts or deletes a line, then for each
matched line runs the id-keyed unit diff (remove missing, copy `condition` /
`acquisition_cost_minor` / `asking_price_minor` / `cash_paid_minor` /
`cash_paid_currency` onto a match, append new). The IMEI is not copied onto a
matched unit: a mis-scan is removed and scanned again. The fresh path builds
`model.lines` with their `units` in one assignment and skips the sync.

## A child that carries fields from another table

A child entity sometimes holds display fields that belong to a different
aggregate: `PurchaseOrderLine` carries the product's `currency` and
`tracking_type` (§4.5 rule 3). The mapper reads them through a read-only
many-to-one relationship the specification eager-loads, never through a
manual join in a query service:

```python
class PurchaseOrderLineModel(TenantBase):
    ...
    product: Mapped[ProductModel] = relationship(lazy="raise", viewonly=True)
```

```python
def _line_to_entity(self, model: PurchaseOrderLineModel) -> PurchaseOrderLine:
    currency = Currency(model.product.currency)
    return PurchaseOrderLine(..., currency=currency,
                             tracking_type=TrackingType(model.product.tracking_type))
```

`viewonly=True` because the line never writes the product back. The spec
chains the load: `selectinload(PurchaseOrderModel.lines).selectinload(
PurchaseOrderLineModel.product)`. `PurchaseOrder` is the reference for this
case.

The relationship may be nullable: `SupplierReturnLine.imei` comes from a
`device_unit` relationship that is `None` on a quantity line, so
`_line_to_entity` reads `None if model.device_unit is None else
model.device_unit.imei`. Each such relationship is a separate
`selectinload` chain in the spec.

## Editing existing children: pass the write spec to `update()`

When `to_model`'s update branch reads a child collection (to re-price a
line, or to add and remove lines), the handler must call
`repository.update(entity, spec)` with the same locking spec it loaded
through. The bare `update(entity)` re-fetches with `session.get()`, which
does not eager-load, and the just-loaded model is usually already gone from
the session's weak identity map by then, so the collection would come back
unloaded and `lazy="raise"` would fire. See `repositories.md` rule 7.

## Relationships on tenant models

`PurchaseOrder` was the first: `PurchaseOrderModel.lines` (one-to-many,
`cascade="all, delete-orphan"`, `lazy="raise"`) and the line's `product`
(many-to-one, `viewonly=True`, `lazy="raise"`). `SupplierReturn` adds a
nullable `device_unit` on the line for the same reason. `add()` on the generic
repository does a bare `session.add()` and lets the commit flush the graph
through the cascade; the old `_insert` flush that pinned insert order is not
needed once the relationship tells SQLAlchemy the parent comes first.

Declare every collection `lazy="raise"` so a specification that forgets to
eager-load it fails at the query instead of as a silent N+1 or a
`MissingGreenlet` inside a domain method. `GoodsReceipt` (receipt → lines →
units) needs two such collections.
