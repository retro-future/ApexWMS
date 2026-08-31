# Below-cost accessory alert — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Warn a store when an accessory's weighted-average cost has risen to or above its catalog price, so a forgotten reprice does not bleed loss on every sale.

**Architecture:** Two read paths, no domain change and no new stored column. (1) After `ReceiptPoster.receive` posts a goods receipt, a new `BelowCostChecker` application service replays each accessory line's cost pool at the receipt's location and compares the average unit cost to `Product.default_sale_price`; offending products come back on the confirm response as a new `belowCostAlerts` list. (2) A new read-only report `GET /reports/below-cost` lists every active quantity product whose current average cost at a location is at or above its catalog price, computed in one SQL aggregate over `stock_levels` + `financial_transactions`.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2 (async), Dishka DI, pytest (`asyncio_mode=auto`); Next.js App Router, Mantine, next-intl (en/ru/uz), vitest.

**Spec:** `docs/superpowers/specs/2026-08-31-below-cost-accessory-alert-design.md`

## Global Constraints

- Verification order, backend (run from `backend/`): `uv run ruff check src tests`, then `uv run ty check`, then `uv run pytest`. A red `ty check` is a broken build.
- Verification order, frontend (run from `frontend/`): `pnpm lint`, then `pnpm typecheck`, then `pnpm test`.
- CQRS: one `Query` + one `IRequestHandler` per file under `application/queries/`. No module-level `_helper` functions in a query module.
- One response payload class per file under `application/models/`, its factory named `from_entity`, re-exported alphabetically from `application/models/__init__.py`.
- A projection read used by more than one caller is a query service behind a `Protocol` in `application/ports/tenant/queries.py`, implemented in `infrastructure/persistence/tenant/queries/`, wired by one hand-written `@provide` in `di/providers/tenant_repositories.py`. It takes only `TenantSession`.
- Money is integer minor units. `Money` refuses non-int; Postgres `SUM(BIGINT)` widens to `NUMERIC`, so cast with `int(... or 0)` before building `Money`.
- Every new UI string goes into all three of `frontend/messages/en.json`, `ru.json`, `uz.json`.
- No hardcoded colors/spacing in frontend; use Mantine theme tokens.
- Commit after every task with a Conventional Commit subject under 70 chars. End commit messages with:
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01WVoKUFC62crXpNwqCzdqsc
  ```

---

## File Structure

New backend files:

- `backend/src/application/services/below_cost.py` — `BelowCostChecker` service + `BelowCostAlert` dataclass carrier.
- `backend/src/application/models/below_cost_alert.py` — `BelowCostAlertData` response row for the confirm payload.
- `backend/src/application/dtos/below_cost.py` — `BelowCostRow` read row for the report.
- `backend/src/application/queries/list_below_cost.py` — `ListBelowCostQuery` + `ListBelowCostHandler`.
- `backend/src/application/models/below_cost.py` — `BelowCostRowData` report response row.
- `backend/src/infrastructure/persistence/tenant/queries/below_cost.py` — `SqlBelowCostQueries`.
- `backend/tests/application/test_below_cost_alert.py` — application tests for the checker + confirm wiring.
- `backend/tests/api/test_below_cost_report_api.py` — real-DB API test for the report.

New frontend files:

- `frontend/src/app/(app)/reports/below-cost/page.tsx`
- `frontend/src/app/(app)/reports/below-cost/BelowCostList.tsx`
- `frontend/src/app/(app)/reports/below-cost/BelowCostList.test.tsx`

Changed backend files:

- `backend/src/application/services/__init__.py` — export `BelowCostChecker`, `BelowCostAlert`.
- `backend/src/application/models/__init__.py` — export `BelowCostAlertData`, `BelowCostRowData`.
- `backend/src/application/models/goods_receipt.py` — add `below_cost_alerts` field + `from_entity` param.
- `backend/src/application/commands/confirm_goods_receipt.py` — inject `BelowCostChecker`, call it, pass alerts to the payload.
- `backend/src/application/dtos/__init__.py` — export `BelowCostRow`.
- `backend/src/application/ports/tenant/queries.py` — add `BelowCostQueries` Protocol.
- `backend/src/application/ports/__init__.py` — export `BelowCostQueries` (follow how `StockOnHandQueries` is exported).
- `backend/src/application/sorting.py` — add `BelowCostSort`.
- `backend/src/infrastructure/persistence/tenant/queries/__init__.py` — export `SqlBelowCostQueries`.
- `backend/src/di/providers/services.py` — add `BelowCostChecker` to `provide_all`.
- `backend/src/di/providers/tenant_repositories.py` — add `below_cost_queries` `@provide`.
- `backend/src/di/providers/handlers.py` — add `ListBelowCostHandler` to `provide_all` and its import.
- `backend/src/presentation/routers/reports.py` — add `GET /reports/below-cost`.
- `.claude/feature-map.md` — add the report to the Reporting section.

Changed frontend files:

- `frontend/src/lib/types.ts` — add `BelowCostRow` and the `belowCostAlerts` field on the goods receipt type (or regenerate if the client is generated — check first).
- `frontend/src/components/shell/NavLinks.tsx` — add the nav entry.
- `frontend/src/app/(app)/goods-receipts/[id]/` detail component — render the alerts after a successful confirm.
- `frontend/messages/en.json`, `ru.json`, `uz.json` — new strings.

---

## Task 1: `BelowCostChecker` service

**Files:**
- Create: `backend/src/application/services/below_cost.py`
- Modify: `backend/src/application/services/__init__.py`
- Test: `backend/tests/application/test_below_cost_alert.py`

**Interfaces:**
- Consumes: `CostPoolReader.pool_for(product_id: UUID, location_id: UUID) -> CostPool | None` (from `application/services/cost_pools.py`); `CostPool.average_unit_cost -> Money | None`; `TenantDbRepository[Product, ProductModel].get(id) -> Product | None`; `GoodsReceipt.lines: list[GoodsReceiptLine]` where `GoodsReceiptLine.is_serial: bool`, `.product_id: UUID`; `GoodsReceipt.location_id: UUID`.
- Produces:
  ```python
  @dataclass(frozen=True, slots=True)
  class BelowCostAlert:
      product_id: UUID
      sku: str
      catalog_price: Money
      average_unit_cost: Money

  class BelowCostChecker:
      async def alerts_for(self, receipt: GoodsReceipt) -> list[BelowCostAlert]: ...
  ```

- [ ] **Step 1: Write the failing test**

Add to a new file `backend/tests/application/test_below_cost_alert.py`. Look at `backend/tests/application/test_goods_receipt.py` for how a `World` is built and how a receipt is created, scanned, priced and confirmed; reuse that harness. The `World` already exposes fake `products`, `movements`, `transactions`, and a `CostPoolReader` (or build one from those fakes the way `InvoicePoster` tests do).

```python
async def test_alert_when_new_batch_lifts_average_above_catalog_price(world):
    # accessory priced in the catalog at 10_00
    product = await make_accessory(world, sku="CASE-X", default_sale_price_minor=1000)

    # batch 1: 10 @ 6_00 -> average 6_00, below catalog price, no alert
    await receive_accessory(world, product, quantity=10, unit_cost_minor=600)
    checker = BelowCostChecker(world.products, world.cost_pool_reader)
    receipt1 = world.last_receipt
    assert await checker.alerts_for(receipt1) == []

    # batch 2: 10 @ 14_00 -> pool 20 @ (60_00 + 140_00) = 200_00 -> average 10_00
    receipt2 = await receive_accessory(world, product, quantity=10, unit_cost_minor=1400)
    alerts = await checker.alerts_for(receipt2)
    assert len(alerts) == 1
    assert alerts[0].product_id == product.id
    assert alerts[0].sku == "CASE-X"
    assert alerts[0].catalog_price.amount_minor == 1000
    assert alerts[0].average_unit_cost.amount_minor == 1000  # >= triggers


async def test_no_alert_for_serialized_lines_or_unpriced_products(world):
    product = await make_accessory(world, sku="NOPRICE", default_sale_price_minor=None)
    receipt = await receive_accessory(world, product, quantity=5, unit_cost_minor=900)
    checker = BelowCostChecker(world.products, world.cost_pool_reader)
    assert await checker.alerts_for(receipt) == []
```

Write the small `make_accessory` / `receive_accessory` helpers at the top of the test file (a confirmed goods receipt against a QUANTITY product at a fixed location), modelled on the receipt helpers already in `test_goods_receipt.py`. If `world` does not already expose `cost_pool_reader`, add a property to the test `World` that builds `CostPoolReader(world.products, world.movements, world.transactions)`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/application/test_below_cost_alert.py -v`
Expected: FAIL — `ImportError` / `BelowCostChecker` not defined.

- [ ] **Step 3: Write the implementation**

`backend/src/application/services/below_cost.py`:

```python
"""Accessories whose weighted-average cost has caught up to their catalog price.

Selling below cost is sometimes deliberate (clearance, damage). This never
blocks; it makes the case visible. The pool is replayed from the ledgers
(``CostPoolReader``), not read from a column — there is none.
"""

from dataclasses import dataclass
from uuid import UUID

from application.common.repository import TenantDbRepository
from application.services.cost_pools import CostPoolReader
from domain.entities import GoodsReceipt, Product
from domain.value_objects import Money
from infrastructure.persistence.tenant.models import ProductModel


@dataclass(frozen=True, slots=True)
class BelowCostAlert:
    product_id: UUID
    sku: str
    catalog_price: Money
    average_unit_cost: Money


class BelowCostChecker:
    def __init__(
        self,
        products: TenantDbRepository[Product, ProductModel],
        pools: CostPoolReader,
    ) -> None:
        self._products = products
        self._pools = pools

    async def alerts_for(self, receipt: GoodsReceipt) -> list[BelowCostAlert]:
        seen: set[UUID] = set()
        alerts: list[BelowCostAlert] = []
        for line in receipt.lines:
            if line.is_serial or line.product_id in seen:
                continue
            seen.add(line.product_id)
            alert = await self._alert_for(line.product_id, receipt.location_id)
            if alert is not None:
                alerts.append(alert)
        return alerts

    async def _alert_for(
        self, product_id: UUID, location_id: UUID
    ) -> BelowCostAlert | None:
        product = await self._products.get(product_id)
        if product is None or product.default_sale_price is None:
            return None
        pool = await self._pools.pool_for(product_id, location_id)
        if pool is None:
            return None
        average = pool.average_unit_cost
        if average is None or average < product.default_sale_price:
            return None
        return BelowCostAlert(
            product_id=product_id,
            sku=str(product.sku),
            catalog_price=product.default_sale_price,
            average_unit_cost=average,
        )
```

Add to `backend/src/application/services/__init__.py`: import `BelowCostChecker`, `BelowCostAlert` from `application.services.below_cost` and add both to `__all__`, keeping the file's existing ordering style.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/application/test_below_cost_alert.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: ruff + ty**

Run: `uv run ruff check src tests && uv run ty check`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add backend/src/application/services/below_cost.py backend/src/application/services/__init__.py backend/tests/application/test_below_cost_alert.py
git commit -m "feat: BelowCostChecker for accessories at or above catalog price"
```

---

## Task 2: `belowCostAlerts` on the goods receipt confirm response

**Files:**
- Create: `backend/src/application/models/below_cost_alert.py`
- Modify: `backend/src/application/models/__init__.py`, `backend/src/application/models/goods_receipt.py`, `backend/src/application/commands/confirm_goods_receipt.py`, `backend/src/di/providers/services.py`
- Test: `backend/tests/application/test_below_cost_alert.py` (add cases)

**Interfaces:**
- Consumes: `BelowCostChecker.alerts_for(receipt) -> list[BelowCostAlert]` (Task 1); `BelowCostAlert` fields (Task 1); `GoodsReceiptData.from_entity(receipt, *, show_cost)` (existing).
- Produces:
  ```python
  class BelowCostAlertData(CamelModel):
      product_id: UUID
      sku: str
      catalog_price: Decimal
      catalog_price_minor: int
      average_unit_cost: Decimal
      average_unit_cost_minor: int

      @classmethod
      def from_entity(cls, alert: BelowCostAlert) -> BelowCostAlertData: ...
  ```
  `GoodsReceiptData` gains `below_cost_alerts: list[BelowCostAlertData] = []`, populated only by the confirm handler.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/application/test_below_cost_alert.py`. Drive the real `ConfirmGoodsReceiptHandler` the way `test_goods_receipt.py` does (build the command, call `handler.handle`).

```python
async def test_confirm_goods_receipt_returns_below_cost_alert(world):
    product = await make_accessory(world, sku="CASE-X", default_sale_price_minor=1000)
    await receive_accessory(world, product, quantity=10, unit_cost_minor=600)

    receipt = await draft_accessory_receipt(world, product, quantity=10, unit_cost_minor=1400)
    result = await confirm_receipt(world, receipt.id)  # uses ConfirmGoodsReceiptHandler

    assert result.success
    assert result.data is not None
    alerts = result.data.below_cost_alerts
    assert len(alerts) == 1
    assert alerts[0].sku == "CASE-X"
    assert alerts[0].catalog_price_minor == 1000
    assert alerts[0].average_unit_cost_minor == 1000
    # receipt still confirmed
    assert result.data.status.value == "confirmed"


async def test_confirm_returns_no_alert_when_below_cost(world):
    product = await make_accessory(world, sku="OK", default_sale_price_minor=5000)
    receipt = await draft_accessory_receipt(world, product, quantity=3, unit_cost_minor=900)
    result = await confirm_receipt(world, receipt.id)
    assert result.data is not None
    assert result.data.below_cost_alerts == []
```

`confirm_receipt` builds `ConfirmGoodsReceiptHandler` with the `world` fakes plus a `BelowCostChecker(world.products, world.cost_pool_reader)`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/application/test_below_cost_alert.py -k confirm -v`
Expected: FAIL — `ConfirmGoodsReceiptHandler.__init__` takes no `checker`, or `GoodsReceiptData` has no `below_cost_alerts`.

- [ ] **Step 3: Write `BelowCostAlertData`**

`backend/src/application/models/below_cost_alert.py`:

```python
"""One accessory whose average cost has reached its catalog price — the alert
attached to a Goods Receipt confirm response (see the design doc).

Not behind ``Permission.Cost.View``: the whole point is that the person
confirming the receipt sees the mismatch. The figures are a comparison the
store needs, not the receipt's own line costs.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from application.services import BelowCostAlert


class BelowCostAlertData(CamelModel):
    product_id: UUID
    sku: str
    catalog_price: Decimal
    catalog_price_minor: int
    average_unit_cost: Decimal
    average_unit_cost_minor: int

    @classmethod
    def from_entity(cls, alert: BelowCostAlert) -> BelowCostAlertData:
        return cls(
            product_id=alert.product_id,
            sku=alert.sku,
            catalog_price=alert.catalog_price.as_major(),
            catalog_price_minor=alert.catalog_price.amount_minor,
            average_unit_cost=alert.average_unit_cost.as_major(),
            average_unit_cost_minor=alert.average_unit_cost.amount_minor,
        )
```

Confirm the `Money` accessor name: Task 1's reference (`GoodsReceiptLineData`) uses `line.unit_cost.as_major()` and `.amount_minor` — use the same two.

Add `BelowCostAlertData` to `application/models/__init__.py` imports and `__all__`, alphabetized.

- [ ] **Step 4: Add the field to `GoodsReceiptData`**

In `backend/src/application/models/goods_receipt.py`:

- import `BelowCostAlertData` from `application.models.below_cost_alert`, and `BelowCostAlert` from `application.services` under `TYPE_CHECKING` if only used as a hint (it is used in the signature below, so a runtime import is fine — match the file's existing import style).
- Add to `GoodsReceiptData`:
  ```python
  # Populated only by the confirm handler (see the below-cost design doc);
  # empty on get/list/create/cancel.
  below_cost_alerts: list[BelowCostAlertData] = []
  ```
- Change the signature to:
  ```python
  @classmethod
  def from_entity(
      cls,
      receipt: GoodsReceipt,
      *,
      show_cost: bool,
      below_cost_alerts: list[BelowCostAlert] | None = None,
  ) -> GoodsReceiptData:
  ```
- Build the list in the body before the `show_cost` branch:
  ```python
  alerts = [BelowCostAlertData.from_entity(one) for one in (below_cost_alerts or [])]
  ```
  and pass `below_cost_alerts=alerts` into the `cls(...)` call.

- [ ] **Step 5: Wire the confirm handler**

In `backend/src/application/commands/confirm_goods_receipt.py`:

- import `BelowCostChecker` from `application.services`.
- add constructor param `checker: BelowCostChecker` and store as `self._checker`.
- in `handle`, after `await self._poster.receive(receipt)` and before `await self._receipts.update(...)`:
  ```python
  alerts = await self._checker.alerts_for(receipt)
  ```
- pass it to the payload:
  ```python
  return ResultWithData[GoodsReceiptData].succeed_with_data(
      GoodsReceiptData.from_entity(
          receipt,
          show_cost=Permission.COST_VIEW in self._current.permissions,
          below_cost_alerts=alerts,
      )
  )
  ```

In `backend/src/di/providers/services.py`: add `BelowCostChecker` to the `provide_all(...)` list (near `ReceiptPoster`) and to the import block from `application.services`.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/application/test_below_cost_alert.py tests/application/test_goods_receipt.py -v`
Expected: PASS. Fix any existing `GoodsReceiptData.from_entity` call sites the new keyword broke — it is keyword-only with a default, so none should break; if `ty` flags one, it is a real call that passed positionally.

- [ ] **Step 7: ruff + ty + full application suite**

Run: `uv run ruff check src tests && uv run ty check && uv run pytest tests/application -q`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add backend/src/application/models/below_cost_alert.py backend/src/application/models/__init__.py backend/src/application/models/goods_receipt.py backend/src/application/commands/confirm_goods_receipt.py backend/src/di/providers/services.py backend/tests/application/test_below_cost_alert.py
git commit -m "feat: return below-cost alerts on goods receipt confirm"
```

---

## Task 3: `SqlBelowCostQueries` and the port

**Files:**
- Create: `backend/src/application/dtos/below_cost.py`, `backend/src/infrastructure/persistence/tenant/queries/below_cost.py`
- Modify: `backend/src/application/dtos/__init__.py`, `backend/src/application/ports/tenant/queries.py`, `backend/src/application/ports/__init__.py`, `backend/src/application/sorting.py`, `backend/src/infrastructure/persistence/tenant/queries/__init__.py`, `backend/src/di/providers/tenant_repositories.py`
- Test: `backend/tests/api/test_below_cost_report_api.py` (written in Task 5; this task has no unit test because the read is a real-DB join — see note)

**Interfaces:**
- Consumes: `TenantSession`; `ProductModel` (`id`, `sku`, `name`, `brand`, `currency`, `tracking_type`, `default_sale_price_minor`, `is_active`), `StockLevelModel` (`product_id`, `location_id`, `quantity`), `LocationModel` (`id`, `name`), `FinancialTransactionModel` (`product_id`, `location_id`, `device_unit_id`, `txn_type`, `amount_minor`). Confirm `ProductModel.is_active` exists (it extends `TenantActivatableRow`); confirm `StockLevelModel` column names against `backend/src/infrastructure/persistence/tenant/models/stock_level.py`.
- Produces:
  ```python
  @dataclass(frozen=True, slots=True)
  class BelowCostRow:
      product_id: UUID
      sku: str
      product_name: str
      location_id: UUID
      location_name: str
      quantity: int
      catalog_price: Money
      average_unit_cost: Money

      @property
      def shortfall(self) -> Money: ...   # average_unit_cost - catalog_price

  class BelowCostQueries(Protocol):
      async def list_below_cost(
          self, page: int, page_size: int,
          location_id: UUID | None = None,
          sort: BelowCostSort = BelowCostSort.SHORTFALL,
      ) -> tuple[list[BelowCostRow], int]: ...

  class BelowCostSort(StrEnum):
      SHORTFALL = "shortfall"
      SKU = "sku"
  ```

- [ ] **Step 1: Add `BelowCostSort`**

In `backend/src/application/sorting.py`, after `AgeingSort`:

```python
class BelowCostSort(StrEnum):
    SHORTFALL = "shortfall"
    SKU = "sku"
```

- [ ] **Step 2: Add the read row DTO**

`backend/src/application/dtos/below_cost.py`:

```python
"""One accessory carried at or above its catalog price, at one location (FR-9.x).

A read row, not an entity: the report flattens the catalog row, the level
and the location, and its cost is a pool the ledger implies, not a column.
"""

from dataclasses import dataclass
from uuid import UUID

from domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class BelowCostRow:
    product_id: UUID
    sku: str
    product_name: str
    location_id: UUID
    location_name: str
    quantity: int
    catalog_price: Money
    average_unit_cost: Money

    @property
    def shortfall(self) -> Money:
        return self.average_unit_cost - self.catalog_price
```

Add `BelowCostRow` to `application/dtos/__init__.py`, alphabetized, matching the existing export style.

- [ ] **Step 3: Add the port**

In `backend/src/application/ports/tenant/queries.py`:

- add `from application.dtos import ... BelowCostRow ...` to the existing dtos import, alphabetized.
- add `from application.sorting import AgeingSort, BelowCostSort, DeviationSort`.
- add the Protocol (place it near `StockOnHandQueries`):
  ```python
  class BelowCostQueries(Protocol):
      """Active accessories whose weighted-average cost has reached their
      catalog price. Its own port: the read spans ``stock_levels`` and the
      money ledger, and neither aggregate owns the other's half. The average
      is ``sum(amount_minor * INVENTORY_SIGN) / quantity`` over the pair —
      the same fold as ``services/cost_pools.py``'s ``INVENTORY_SIGN``, so
      the report and a real sale agree about the same goods."""

      async def list_below_cost(
          self,
          page: int,
          page_size: int,
          location_id: UUID | None = None,
          sort: BelowCostSort = BelowCostSort.SHORTFALL,
      ) -> tuple[list[BelowCostRow], int]: ...
  ```

Add `BelowCostQueries` to `application/ports/__init__.py` (find where `StockOnHandQueries` is re-exported and mirror it).

- [ ] **Step 4: Implement `SqlBelowCostQueries`**

`backend/src/infrastructure/persistence/tenant/queries/below_cost.py`:

```python
"""Accessories at or above their catalog price (see the below-cost design doc).

The average unit cost is rebuilt in SQL, not via ``CostPoolReader``: a store
has hundreds of accessories across locations, and replaying every pool per
request is too much. Pool value for a (product, location) pair equals
``sum(amount_minor * INVENTORY_SIGN[txn_type])`` over the money ledger —
identical to the fold in ``application/services/cost_pools.py``. Keep the
CASE below in step with that table.
"""

from uuid import UUID

from sqlalchemy import Row, and_, case, func, select

from application.dtos import BelowCostRow
from application.sorting import BelowCostSort
from domain.enums import TrackingType, TransactionType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    FinancialTransactionModel,
    LocationModel,
    ProductModel,
    StockLevelModel,
)
from infrastructure.types import TenantSession

# amount_minor is signed by §4.6's cash direction; INVENTORY_SIGN flips the
# two categories whose cash sign is opposite their effect on shelf value.
_POOL_VALUE = func.sum(
    case(
        (FinancialTransactionModel.txn_type == TransactionType.PURCHASE.value,
         -FinancialTransactionModel.amount_minor),
        (FinancialTransactionModel.txn_type == TransactionType.COGS.value,
         FinancialTransactionModel.amount_minor),
        (FinancialTransactionModel.txn_type == TransactionType.WRITE_OFF_LOSS.value,
         FinancialTransactionModel.amount_minor),
        (FinancialTransactionModel.txn_type == TransactionType.SUPPLIER_RETURN_CREDIT.value,
         -FinancialTransactionModel.amount_minor),
        (FinancialTransactionModel.txn_type == TransactionType.COUNT_ADJUSTMENT.value,
         FinancialTransactionModel.amount_minor),
        else_=0,
    )
)


class SqlBelowCostQueries:
    def __init__(self, session: TenantSession) -> None:
        self._session = session

    async def list_below_cost(
        self,
        page: int,
        page_size: int,
        location_id: UUID | None = None,
        sort: BelowCostSort = BelowCostSort.SHORTFALL,
    ) -> tuple[list[BelowCostRow], int]:
        value_minor = _POOL_VALUE.label("value_minor")
        stmt = (
            select(
                ProductModel.id,
                ProductModel.sku,
                ProductModel.name,
                ProductModel.currency,
                ProductModel.default_sale_price_minor,
                StockLevelModel.location_id,
                LocationModel.name,
                StockLevelModel.quantity,
                value_minor,
            )
            .join(ProductModel, ProductModel.id == StockLevelModel.product_id)
            .join(LocationModel, LocationModel.id == StockLevelModel.location_id)
            .outerjoin(
                FinancialTransactionModel,
                and_(
                    FinancialTransactionModel.product_id == StockLevelModel.product_id,
                    FinancialTransactionModel.location_id == StockLevelModel.location_id,
                    FinancialTransactionModel.device_unit_id.is_(None),
                ),
            )
            .where(
                ProductModel.tracking_type == TrackingType.QUANTITY.value,
                ProductModel.is_active.is_(True),
                ProductModel.default_sale_price_minor.is_not(None),
                StockLevelModel.quantity > 0,
            )
            .group_by(
                ProductModel.id,
                ProductModel.sku,
                ProductModel.name,
                ProductModel.currency,
                ProductModel.default_sale_price_minor,
                StockLevelModel.location_id,
                LocationModel.name,
                StockLevelModel.quantity,
            )
            # average >= price  <=>  value >= price * quantity  (quantity > 0),
            # exact, no rounding.
            .having(value_minor >= ProductModel.default_sale_price_minor * StockLevelModel.quantity)
        )
        if location_id is not None:
            stmt = stmt.where(StockLevelModel.location_id == location_id)

        ordered = self._ordered(stmt, sort, value_minor)
        rows = list(await self._session.execute(
            ordered.limit(page_size).offset((page - 1) * page_size)
        ))
        total = await self._count(stmt)
        return [self._to_row(row) for row in rows], total

    @staticmethod
    def _ordered(stmt, sort: BelowCostSort, value_minor):
        if sort is BelowCostSort.SKU:
            return stmt.order_by(ProductModel.sku)
        # shortfall = average - price; order by (value/quantity - price) desc.
        # Ordering by value_minor - price*quantity is monotone in the same
        # direction and needs no division.
        return stmt.order_by(
            (value_minor - ProductModel.default_sale_price_minor * StockLevelModel.quantity).desc()
        )

    async def _count(self, stmt) -> int:
        subq = stmt.order_by(None).subquery()
        return int(await self._session.scalar(select(func.count()).select_from(subq)) or 0)

    @staticmethod
    def _to_row(row: Row) -> BelowCostRow:
        (product_id, sku, name, currency_code, price_minor,
         location_id, location_name, quantity, value_minor) = row._tuple()
        currency = Currency(currency_code)
        pool_value = int(value_minor or 0)
        average_minor = round(pool_value / quantity)
        return BelowCostRow(
            product_id=product_id,
            sku=sku,
            product_name=name,
            location_id=location_id,
            location_name=location_name,
            quantity=quantity,
            catalog_price=Money(int(price_minor), currency),
            average_unit_cost=Money(average_minor, currency),
        )
```

Note on `round`: Python's `round` is banker's rounding; `CostPool.average_unit_cost` uses `_round_half_up`. For a display figure on a warning report the difference is at most one minor unit and never changes whether a row appears (the `HAVING` clause is exact). If the reviewer wants an exact match, import and reuse `_round_half_up` from `domain.value_objects.cost_pool` — decide during review.

Add `SqlBelowCostQueries` to `backend/src/infrastructure/persistence/tenant/queries/__init__.py` exports.

- [ ] **Step 5: DI wiring**

In `backend/src/di/providers/tenant_repositories.py`:
- add `BelowCostQueries` to the `from application.ports import (...)` block.
- add `SqlBelowCostQueries` to the `from infrastructure.persistence.tenant.queries import (...)` block.
- add the provider method near `stock_on_hand_queries`:
  ```python
  @provide
  def below_cost_queries(self, session: TenantSession) -> BelowCostQueries:
      return SqlBelowCostQueries(session)
  ```

- [ ] **Step 6: ruff + ty**

Run: `uv run ruff check src && uv run ty check`
Expected: clean. `ty` will not check the SQL, but it checks the port/impl/DI shapes line up.

- [ ] **Step 7: Commit**

```bash
git add backend/src/application/dtos/below_cost.py backend/src/application/dtos/__init__.py backend/src/application/ports/ backend/src/application/sorting.py backend/src/infrastructure/persistence/tenant/queries/below_cost.py backend/src/infrastructure/persistence/tenant/queries/__init__.py backend/src/di/providers/tenant_repositories.py
git commit -m "feat: SqlBelowCostQueries reads accessories at or above catalog price"
```

---

## Task 4: `ListBelowCostQuery` handler + model

**Files:**
- Create: `backend/src/application/queries/list_below_cost.py`, `backend/src/application/models/below_cost.py`
- Modify: `backend/src/application/models/__init__.py`, `backend/src/di/providers/handlers.py`
- Test: `backend/tests/application/test_below_cost_alert.py` (add a handler test with a fake queries object)

**Interfaces:**
- Consumes: `BelowCostQueries.list_below_cost(...)` (Task 3); `BelowCostRow` fields + `.shortfall` (Task 3); `PagedQuery`, `PagedResult` from `application.core`.
- Produces:
  ```python
  class ListBelowCostQuery(PagedQuery[PagedResult[BelowCostRowData]]):
      location_id: UUID | None = None
      sort: BelowCostSort = BelowCostSort.SHORTFALL

  class ListBelowCostHandler(IRequestHandler[PagedResult[BelowCostRowData], ListBelowCostQuery]): ...

  class BelowCostRowData(CamelModel):
      # product_id, sku, product_name, location_id, location_name, quantity,
      # catalog_price(+_minor), average_unit_cost(+_minor), shortfall(+_minor)
      @classmethod
      def from_entity(cls, row: BelowCostRow) -> BelowCostRowData: ...
  ```

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/application/test_below_cost_alert.py`:

```python
class _FakeBelowCostQueries:
    def __init__(self, rows: list[BelowCostRow]) -> None:
        self._rows = rows

    async def list_below_cost(self, page, page_size, location_id=None, sort=BelowCostSort.SHORTFALL):
        start = (page - 1) * page_size
        return self._rows[start : start + page_size], len(self._rows)


async def test_list_below_cost_handler_maps_rows():
    row = BelowCostRow(
        product_id=uuid4(), sku="CASE-X", product_name="Case X",
        location_id=uuid4(), location_name="Main",
        quantity=20,
        catalog_price=Money(1000, Currency.USD),
        average_unit_cost=Money(1100, Currency.USD),
    )
    handler = ListBelowCostHandler(_FakeBelowCostQueries([row]))
    result = await handler.handle(ListBelowCostQuery(page=1, page_size=25))
    assert result.success
    assert result.total_items == 1
    one = result.data[0]
    assert one.sku == "CASE-X"
    assert one.catalog_price_minor == 1000
    assert one.average_unit_cost_minor == 1100
    assert one.shortfall_minor == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/application/test_below_cost_alert.py -k list_below_cost -v`
Expected: FAIL — imports undefined.

- [ ] **Step 3: Write `BelowCostRowData`**

`backend/src/application/models/below_cost.py`:

```python
"""One row of the below-cost report (see the below-cost design doc).

No ``Permission.Cost.View`` gate: the report is the cost picture — trimming
its figures would leave an empty table. It sits behind
``Permission.Reporting.View`` like the other worklists.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from application.dtos import BelowCostRow


class BelowCostRowData(CamelModel):
    product_id: UUID
    sku: str
    product_name: str
    location_id: UUID
    location_name: str
    quantity: int
    catalog_price: Decimal
    catalog_price_minor: int
    average_unit_cost: Decimal
    average_unit_cost_minor: int
    shortfall: Decimal
    shortfall_minor: int

    @classmethod
    def from_entity(cls, row: BelowCostRow) -> BelowCostRowData:
        return cls(
            product_id=row.product_id,
            sku=row.sku,
            product_name=row.product_name,
            location_id=row.location_id,
            location_name=row.location_name,
            quantity=row.quantity,
            catalog_price=row.catalog_price.as_major(),
            catalog_price_minor=row.catalog_price.amount_minor,
            average_unit_cost=row.average_unit_cost.as_major(),
            average_unit_cost_minor=row.average_unit_cost.amount_minor,
            shortfall=row.shortfall.as_major(),
            shortfall_minor=row.shortfall.amount_minor,
        )
```

Add `BelowCostRowData` to `application/models/__init__.py`, alphabetized.

- [ ] **Step 4: Write the handler**

`backend/src/application/queries/list_below_cost.py` — model it on `list_needs_pricing.py`:

```python
"""Active accessories carried at or above their catalog price.

FR-2.19 read backwards: a weighted-average pool that has caught up to the
catalog price means every sale of that accessory now books a loss until an
Owner or Manager reprices it. Selling below cost can be deliberate, so this
is a worklist, not a block.
"""

from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import BelowCostRowData
from application.ports import BelowCostQueries
from application.sorting import BelowCostSort


class ListBelowCostQuery(PagedQuery[PagedResult[BelowCostRowData]]):
    location_id: UUID | None = None
    sort: BelowCostSort = BelowCostSort.SHORTFALL


class ListBelowCostHandler(
    IRequestHandler[PagedResult[BelowCostRowData], ListBelowCostQuery]
):
    def __init__(self, below_cost: BelowCostQueries) -> None:
        self._below_cost = below_cost

    async def handle(self, request: ListBelowCostQuery) -> PagedResult[BelowCostRowData]:
        rows, total = await self._below_cost.list_below_cost(
            page=request.page,
            page_size=request.page_size,
            location_id=request.location_id,
            sort=request.sort,
        )
        return PagedResult[BelowCostRowData].succeed_with_data(
            data=[BelowCostRowData.from_entity(row) for row in rows],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
```

- [ ] **Step 5: Register the handler**

In `backend/src/di/providers/handlers.py`: add `from application.queries.list_below_cost import ListBelowCostHandler` in query import order, and add `ListBelowCostHandler` to `provide_all(...)` under the `# --- M8 reporting ---` block.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/application/test_below_cost_alert.py -v && uv run ruff check src tests && uv run ty check`
Expected: PASS + clean.

- [ ] **Step 7: Commit**

```bash
git add backend/src/application/queries/list_below_cost.py backend/src/application/models/below_cost.py backend/src/application/models/__init__.py backend/src/di/providers/handlers.py backend/tests/application/test_below_cost_alert.py
git commit -m "feat: ListBelowCost query handler and response row"
```

---

## Task 5: `GET /reports/below-cost` route + real-DB API test

**Files:**
- Modify: `backend/src/presentation/routers/reports.py`
- Test: `backend/tests/api/test_below_cost_report_api.py`

**Interfaces:**
- Consumes: `ListBelowCostQuery`, `ListBelowCostHandler` (Task 4); `BelowCostRowData` (Task 4); `Permission.REPORTING_VIEW`; `require`, `bearer_scheme` from `presentation.security`.
- Produces: `GET /reports/below-cost -> PagedResult[BelowCostRowData]`.

- [ ] **Step 1: Write the failing API test**

`backend/tests/api/test_below_cost_report_api.py` — model on `backend/tests/api/test_stock_reports_api.py` (same fixtures: a provisioned tenant, an authed client, helpers to create products/locations and to confirm goods receipts and sales). The scenario:

```python
async def test_below_cost_report_lists_accessory_after_price_rise(client, seed):
    loc = await seed.location("Main")
    product = await seed.accessory(sku="CASE-X", currency="USD", default_sale_price_minor=1000)

    await seed.confirm_accessory_receipt(product, loc, quantity=10, unit_cost_minor=600)
    # not listed yet: average 6.00 < 10.00
    r = await client.get("/api/v1/reports/below-cost")
    assert r.status_code == 200
    assert r.json()["data"] == []

    await seed.confirm_accessory_receipt(product, loc, quantity=10, unit_cost_minor=1400)
    # average now 10.00 >= 10.00
    r = await client.get("/api/v1/reports/below-cost")
    body = r.json()
    assert body["totalItems"] == 1
    row = body["data"][0]
    assert row["sku"] == "CASE-X"
    assert row["catalogPriceMinor"] == 1000
    assert row["averageUnitCostMinor"] == 1000
    assert row["quantity"] == 20


async def test_below_cost_report_needs_reporting_permission(client_as_seller):
    r = await client_as_seller.get("/api/v1/reports/below-cost")
    assert r.status_code == 403


async def test_below_cost_report_drops_pair_after_a_sale_brings_average_down(client, seed):
    # optional: sell some units at a location and assert the pair leaves/stays
    # per the maths; keep only if the seed helpers make a sale easy.
    ...
```

Check the exact fixture names in `test_stock_reports_api.py` and reuse them; do not invent a `seed` object if the suite uses free helper functions.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_below_cost_report_api.py -v`
Expected: FAIL — 404 on the route.

- [ ] **Step 3: Add the route**

In `backend/src/presentation/routers/reports.py`:
- add to the `from application.models import (...)` block: `BelowCostRowData`.
- add the import:
  ```python
  from application.queries.list_below_cost import (
      ListBelowCostHandler,
      ListBelowCostQuery,
  )
  ```
- add the endpoint (next to `list_needs_pricing`):
  ```python
  @router.get("/below-cost")
  async def list_below_cost(
      query: Annotated[ListBelowCostQuery, Query()],
      current: FromDishka[CurrentUser],
      handler: FromDishka[ListBelowCostHandler],
  ) -> PagedResult[BelowCostRowData]:
      """Active accessories whose weighted-average cost has reached their
      catalog price — every following sale books a loss until they are
      repriced. A worklist, not a block: selling below cost can be
      deliberate."""
      require(current, Permission.REPORTING_VIEW)
      return await handler.handle(query)
  ```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/api/test_below_cost_report_api.py -v`
Expected: PASS.

- [ ] **Step 5: Full backend gate**

Run: `uv run ruff check src tests && uv run ty check && uv run pytest`
Expected: all green. This is the point where a regression in `test_goods_receipt.py` / `test_reporting.py` / the API suite would show.

- [ ] **Step 6: Update the feature map**

In `.claude/feature-map.md`, the Reporting section: add `list_below_cost.py` to the Queries list, `models/below_cost.py` to Models, `dtos/below_cost.py` to Carriers, `SqlBelowCostQueries` to the reporting-reads paragraph, and `services/below_cost.py` (`BelowCostChecker`) — note it is called from `confirm_goods_receipt.py`. Add `below-cost/` to the Screens folder list.

- [ ] **Step 7: Commit**

```bash
git add backend/src/presentation/routers/reports.py backend/tests/api/test_below_cost_report_api.py .claude/feature-map.md
git commit -m "feat: GET /reports/below-cost endpoint"
```

---

## Task 6: Frontend — below-cost report screen

**Files:**
- Create: `frontend/src/app/(app)/reports/below-cost/page.tsx`, `frontend/src/app/(app)/reports/below-cost/BelowCostList.tsx`, `frontend/src/app/(app)/reports/below-cost/BelowCostList.test.tsx`
- Modify: `frontend/src/lib/types.ts` (or regenerate the API client — check which), `frontend/src/components/shell/NavLinks.tsx`, `frontend/messages/en.json`, `frontend/messages/ru.json`, `frontend/messages/uz.json`

**Interfaces:**
- Consumes: the `GET /reports/below-cost` payload (Task 5) — camelCase fields `productId, sku, productName, locationId, locationName, quantity, catalogPrice, catalogPriceMinor, averageUnitCost, averageUnitCostMinor, shortfall, shortfallMinor`.
- Produces: a route at `/reports/below-cost`.

- [ ] **Step 1: Regenerate or hand-add the type**

Check `frontend/` for a generated client (look for an `openapi` script in `package.json` or a `src/lib/api-types` file). If generated: run the generate script and confirm `BelowCostRow` and the goods-receipt `belowCostAlerts` field appear. If hand-maintained in `src/lib/types.ts`: add

```ts
export interface BelowCostRow {
  productId: string;
  sku: string;
  productName: string;
  locationId: string;
  locationName: string;
  quantity: number;
  catalogPrice: string;
  catalogPriceMinor: number;
  averageUnitCost: string;
  averageUnitCostMinor: number;
  shortfall: string;
  shortfallMinor: number;
}
```

and add `belowCostAlerts: BelowCostAlert[]` (with a `BelowCostAlert` interface: `productId, sku, catalogPrice, catalogPriceMinor, averageUnitCost, averageUnitCostMinor`) to the goods receipt type.

- [ ] **Step 2: Write the failing component test**

`frontend/src/app/(app)/reports/below-cost/BelowCostList.test.tsx` — model on any existing `reports/*/*.test.tsx`; if none exists, model on another list test. Render `<BelowCostList />` with a mocked `useResourceList` returning one row, assert the SKU, the location and the formatted shortfall render.

- [ ] **Step 3: Run test to verify it fails**

Run: `pnpm test src/app/\(app\)/reports/below-cost/BelowCostList.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 4: Build the screen**

`page.tsx`:

```tsx
import { BelowCostList } from "@/app/(app)/reports/below-cost/BelowCostList";

export default function BelowCostPage() {
  return <BelowCostList />;
}
```

`BelowCostList.tsx` — model closely on `NeedsPricingList.tsx` (same `ListShell`, `useResourceList("reports/below-cost", { page, locationId })`, the location `Select` filter, `useDateFormat` not needed here). Columns: Product (SKU + name, `Anchor` to `/products/${row.productId}`), Location, Quantity, Catalog price, Average cost, Shortfall (render with the money formatter the other reports use — check `NeedsPricingList` siblings like `AgeingList.tsx` for the money-format helper). No selection, no bulk action. `title={t("belowCostTitle")}`, `subtitle={t("belowCostSubtitle")}`, `emptyMessage={t("noBelowCost")}`, permission `Permission.Reporting.View`.

- [ ] **Step 5: Nav entry**

In `frontend/src/components/shell/NavLinks.tsx`, in the reports `items` array, add after the `needs-pricing` entry:

```tsx
{
  href: "/reports/below-cost",
  label: t("belowCost"),
  icon: IconTrendingDown,
  permission: Permission.Reporting.View,
},
```

Import `IconTrendingDown` from `@tabler/icons-react` with the other icon imports (or pick another unused Tabler icon if that name is wrong).

- [ ] **Step 6: Strings**

Add to all three `frontend/messages/*.json` under the `reports` namespace: `belowCost`, `belowCostTitle`, `belowCostSubtitle`, `noBelowCost`, `catalogPrice`, `averageCost`, `shortfall`, `quantityOnHand`. English values first; provide real ru/uz translations (the repo is en/ru/uz, not English-only placeholders). Suggested English:
- `belowCost`: "Below cost"
- `belowCostTitle`: "Selling below cost"
- `belowCostSubtitle`: "Accessories whose average cost has reached their catalog price. Reprice them or confirm the sale is deliberate."
- `noBelowCost`: "No accessory is priced below its cost."

- [ ] **Step 7: Run the gates**

Run: `pnpm lint && pnpm typecheck && pnpm test`
Expected: green.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/\(app\)/reports/below-cost/ frontend/src/lib/types.ts frontend/src/components/shell/NavLinks.tsx frontend/messages/
git commit -m "feat: below-cost accessory report screen"
```

---

## Task 7: Frontend — show the alert on goods receipt confirm

**Files:**
- Modify: the goods receipt detail component under `frontend/src/app/(app)/goods-receipts/[id]/` (find the one that calls the confirm mutation), `frontend/messages/*.json`
- Test: the detail component's existing test file, or a new one

**Interfaces:**
- Consumes: the confirm response's `belowCostAlerts` array (Task 2 shape, Task 6 type).
- Produces: a visible, non-blocking alert block after a successful confirm.

- [ ] **Step 1: Find the confirm call**

Search `frontend/src/app/(app)/goods-receipts/` for the confirm mutation (grep `confirm`). Note how it currently handles the success response (toast, redirect, refetch).

- [ ] **Step 2: Write the failing test**

In the detail component's test (model on the existing goods-receipt detail test): mock the confirm response to include one `belowCostAlerts` entry, trigger confirm, assert an alert with the SKU and both prices renders and that it does not block the normal success path (receipt still shows as confirmed).

- [ ] **Step 3: Run test to verify it fails**

Run: `pnpm test <the detail test path>`
Expected: FAIL.

- [ ] **Step 4: Render the alerts**

On a successful confirm, if `response.data.belowCostAlerts.length > 0`, render a Mantine `Alert` (color `yellow`, not `red` — it is a warning, not an error) listing each: SKU, catalog price, new average cost, and an `Anchor` to `/products/${alert.productId}`. Keep the existing success toast/redirect behaviour; the alert is additive. If the screen redirects away on confirm, hold the redirect while alerts are shown and let the user dismiss, or surface the alert on the destination — pick whichever matches the existing UX and note the choice in the commit body.

- [ ] **Step 5: Strings**

Add to all three `frontend/messages/*.json` (namespace `goodsReceipts` or wherever the detail screen's strings live): `belowCostWarningTitle` ("This receipt raised cost above catalog price"), `belowCostWarningBody` ("These accessories now cost at least what they sell for. Reprice them or confirm the loss is intended."), `belowCostWarningRow` ("{sku}: sells at {price}, now costs {cost}").

- [ ] **Step 6: Run the gates**

Run: `pnpm lint && pnpm typecheck && pnpm test`
Expected: green.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/\(app\)/goods-receipts/ frontend/messages/
git commit -m "feat: warn on goods receipt confirm when an accessory sells below cost"
```

---

## Task 8: Remove the scratch `docs/superpowers/` directory

The user asked for `docs/superpowers/` (spec + this plan) to be removed once the work is done. Do this only after Tasks 1-7 are merged/complete and verified.

- [ ] **Step 1: Confirm everything is done**

Run: from `backend/` `uv run ruff check src tests && uv run ty check && uv run pytest`; from `frontend/` `pnpm lint && pnpm typecheck && pnpm test`.
Expected: all green.

- [ ] **Step 2: Remove the directory**

```bash
git rm -r docs/superpowers
git commit -m "chore: drop scratch design/plan docs"
```

The permanent record of this feature is the code, the tests, the feature-map entry, and the commit history on `feature/below-cost-accessory-alert`.

---

## Self-Review

**Spec coverage:**
- Spec §1 "Warning on goods receipt confirm" → Tasks 1, 2 (backend), 7 (frontend).
- Spec §2 "Selling below cost report" → Tasks 3, 4, 5 (backend), 6 (frontend).
- Spec "Decision when the alert fires" → surfaced as UI copy in Tasks 6 and 7 (reprice vs. confirm deliberate); no code beyond the alert itself, matching the spec's "no override flow".
- Spec "Not in this iteration" (no invoice change, no block, no acknowledgement state, no serialized detection, no stored column) → nothing in any task touches invoice confirm, adds a block, adds dismiss state, touches serialized pricing, or adds a column.
- Spec "Testing" bullets → Task 2 (confirm handler alert + still confirms), Task 5 (real-DB API + permission gate), Task 3 note + Task 5 (SQL average vs pool: the API test asserts the same 10.00 the pool maths gives), Task 6/7 (frontend).
- Spec "Files" list → covered by the File Structure section; the spec's open question "which layer owns the check" is resolved: a `BelowCostChecker` service the handler calls after `receive`, so `ReceiptPoster` keeps its single job (spec's stated lean).

**Placeholder scan:** Task 5 Step 1 and Task 6 Step 4 point at "model on the existing X" for framework-shaped test/component scaffolding rather than pasting a full file, because the exact fixture and helper names must be read from the sibling files at implementation time; the behavioural assertions and the non-boilerplate code are given in full. Task 3's optional third test and Task 7 Step 4's redirect handling are marked as decisions to make against existing UX, not skipped work.

**Type consistency:** `BelowCostAlert` (service dataclass, `Money` fields) vs `BelowCostAlertData` (response, `Decimal` + `_minor`) vs `BelowCostRow` (report DTO, `Money` + `.shortfall`) vs `BelowCostRowData` (response, `Decimal` + `_minor`) — four distinct names, used consistently. `list_below_cost` signature is identical in the Protocol (Task 3), the SQL impl (Task 3), the fake (Task 4), and the handler call (Task 4). `average_unit_cost` / `catalog_price` / `shortfall` names match across DTO, model, SQL row builder, and the frontend interface (`averageUnitCost` / `catalogPrice` / `shortfall`).
