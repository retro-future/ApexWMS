# Document and Error Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every user-facing string (UI, errors, printed documents) follows the language picked in the app.

**Architecture:** The `apex_locale` cookie is forwarded by the BFF as an `Accept-Language` header. The backend resolves it to a request-scoped `Locale`. A backend `MessageCatalog` (three TOML files) formats both error `detail` strings and PDF document text for that locale. The frontend keeps rendering `detail` unchanged.

**Tech Stack:** FastAPI, Dishka DI, fpdf2, tomllib (stdlib), Next.js App Router, next-intl.

**Spec:** `docs/superpowers/specs/2026-09-01-document-and-error-localization-design.md`

## Global Constraints

- `domain/` imports nothing outside itself. `Locale`, `MessageCatalog` live in `application/` / `infrastructure/`.
- Dishka providers only construct and delegate; no business `if`, no `raise`, no helper methods (`.claude/rules/backend/providers.md`).
- Verification order in `backend/`: `uv run ruff check src tests`, then `uv run ty check`, then `uv run pytest`. All three must pass before a commit. (`.claude/CLAUDE_PYTHON.md`)
- Frontend gates: `pnpm typecheck && pnpm lint`, then `pnpm test`.
- Locales: `uz` (default), `ru`, `en`. Cookie name `apex_locale`, constant `LOCALE_COOKIE` in `frontend/src/i18n/config.ts`.
- CQRS: one Command/Query + one handler per file; response payloads in `application/models/` (not relevant here, no new payloads).
- Commit message trailer: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` and the `Claude-Session:` line.

---

## Task 1: Backend `Locale` type and parser

**Files:**
- Create: `backend/src/application/localization/__init__.py`
- Create: `backend/src/application/localization/locale.py`
- Test: `backend/tests/application/localization/test_locale.py`

**Interfaces:**
- Produces: `Locale(StrEnum)` with members `UZ="uz"`, `RU="ru"`, `EN="en"`; class attr `Locale.DEFAULT` (aliased to `UZ`); classmethod `Locale.parse(header: str | None) -> Locale`.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from application.localization.locale import Locale

@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("ru", Locale.RU),
        ("ru-RU", Locale.RU),
        ("en-US,en;q=0.9", Locale.EN),
        ("uz", Locale.UZ),
        ("", Locale.UZ),
        (None, Locale.UZ),
        ("fr", Locale.UZ),
        ("  RU  ", Locale.RU),
    ],
)
def test_parse(header, expected):
    assert Locale.parse(header) is expected

def test_default_is_uz():
    assert Locale.DEFAULT is Locale.UZ
```

- [ ] **Step 2: Run test, verify it fails** — `uv run pytest tests/application/localization/test_locale.py -v` → import error.

- [ ] **Step 3: Implement**

```python
from __future__ import annotations

from enum import StrEnum


class Locale(StrEnum):
    UZ = "uz"
    RU = "ru"
    EN = "en"

    @classmethod
    def parse(cls, header: str | None) -> Locale:
        if not header:
            return cls.DEFAULT
        first = header.split(",")[0].strip().lower()
        tag = first.split(";")[0].strip().split("-")[0]
        try:
            return cls(tag)
        except ValueError:
            return cls.DEFAULT


Locale.DEFAULT = Locale.UZ  # type: ignore[attr-defined]
```

If `ty` rejects the attribute assignment, use `DEFAULT = UZ` as a real member alias inside the class body instead.

- [ ] **Step 4: Run tests, verify pass.**

- [ ] **Step 5: `ruff check`, `ty check`, commit.**

```bash
git commit -m "feat(i18n): backend Locale type and Accept-Language parser"
```

---

## Task 2: `MessageCatalog` loader and English catalog

**Files:**
- Create: `backend/src/application/localization/catalog.py`
- Create: `backend/src/application/localization/messages/en.toml`
- Create: `backend/src/application/localization/messages/ru.toml` (copy of en for now)
- Create: `backend/src/application/localization/messages/uz.toml` (copy of en for now)
- Modify: `backend/pyproject.toml` — ensure the `messages/*.toml` files ship in the package (Hatchling `force-include` or `[tool.hatch.build] include`, matching how other non-py assets are handled; check `infrastructure/documents` fonts handling if present).
- Test: `backend/tests/application/localization/test_catalog.py`

**Interfaces:**
- Consumes: `Locale` (Task 1).
- Produces: `MessageCatalog` with `__init__(self, root: Path | None = None)` (defaults to the packaged `messages/` dir) and `render(self, locale: Locale, table: str, key: str, /, **params: object) -> str | None`.
- Produces: `catalog_keys(table: str) -> frozenset[str]` on the class for the parity test, reading the English file.

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path
import pytest
from application.localization.catalog import MessageCatalog
from application.localization.locale import Locale

@pytest.fixture
def catalog(tmp_path: Path) -> MessageCatalog:
    (tmp_path / "en.toml").write_text(
        '[errors]\nboom = "Boom {name}"\n[documents]\ntitle = "Invoice"\n'
    )
    (tmp_path / "ru.toml").write_text('[errors]\nboom = "Бум {name}"\n[documents]\n')
    (tmp_path / "uz.toml").write_text('[errors]\n[documents]\n')
    return MessageCatalog(tmp_path)

def test_render_localized(catalog):
    assert catalog.render(Locale.RU, "errors", "boom", name="x") == "Бум x"

def test_falls_back_to_english(catalog):
    assert catalog.render(Locale.UZ, "errors", "boom", name="x") == "Boom x"

def test_missing_key_returns_none(catalog):
    assert catalog.render(Locale.EN, "errors", "nope") is None

def test_missing_placeholder_returns_template_not_raise(catalog):
    assert catalog.render(Locale.EN, "errors", "boom") == "Boom {name}"
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement**

```python
from __future__ import annotations

import logging
import tomllib
from pathlib import Path

from application.localization.locale import Locale

_LOG = logging.getLogger(__name__)
_DEFAULT_ROOT = Path(__file__).parent / "messages"


class MessageCatalog:
    def __init__(self, root: Path | None = None) -> None:
        base = root or _DEFAULT_ROOT
        self._data: dict[Locale, dict[str, dict[str, str]]] = {}
        for locale in Locale:
            raw = tomllib.loads((base / f"{locale.value}.toml").read_text("utf-8"))
            self._data[locale] = {
                table: dict(entries) for table, entries in raw.items()
            }

    def render(
        self, locale: Locale, table: str, key: str, /, **params: object
    ) -> str | None:
        template = self._lookup(locale, table, key) or self._lookup(
            Locale.EN, table, key
        )
        if template is None:
            return None
        try:
            return template.format(**params)
        except (KeyError, IndexError):
            _LOG.warning("message %s.%s missing a placeholder value", table, key)
            return template

    def _lookup(self, locale: Locale, table: str, key: str) -> str | None:
        return self._data.get(locale, {}).get(table, {}).get(key)

    def keys(self, table: str) -> frozenset[str]:
        return frozenset(self._data[Locale.EN].get(table, {}))
```

- [ ] **Step 4: Seed `en.toml`** with the `[documents]` keys the renderers need (see Task 7 for the exact list) and a `[errors]` table that starts empty (filled in Task 5/6). Copy `en.toml` to `ru.toml` and `uz.toml`.

- [ ] **Step 5: Run tests, `ruff`, `ty`, verify the packaged path resolves (`uv run python -c "from application.localization.catalog import MessageCatalog; MessageCatalog()"`).**

- [ ] **Step 6: Commit** — `feat(i18n): MessageCatalog loader with TOML message files`

---

## Task 3: Locale DI provider

**Files:**
- Create: `backend/src/infrastructure/localization/__init__.py`
- Create: `backend/src/infrastructure/localization/current_locale_accessor.py`
- Create: `backend/src/di/providers/localization.py`
- Modify: `backend/src/di/providers/__init__.py` (export `LocalizationProvider`)
- Modify: `backend/src/di/container.py` (add `LocalizationProvider()` to the list)
- Test: `backend/tests/application/localization/test_current_locale_accessor.py`

**Interfaces:**
- Consumes: `Locale` (Task 1), `MessageCatalog` (Task 2).
- Produces: `CurrentLocaleAccessor(request: Request)` with `get_locale() -> Locale`.
- Produces: DI resolutions — `Locale` (REQUEST scope), `CurrentLocaleAccessor` (REQUEST scope), `MessageCatalog` (APP scope).

- [ ] **Step 1: Failing test**

```python
from starlette.requests import Request
from application.localization.locale import Locale
from infrastructure.localization.current_locale_accessor import CurrentLocaleAccessor

def _request(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request({"type": "http", "headers": headers})

def test_reads_accept_language():
    acc = CurrentLocaleAccessor(_request([(b"accept-language", b"ru")]))
    assert acc.get_locale() is Locale.RU

def test_defaults_when_absent():
    assert CurrentLocaleAccessor(_request([])).get_locale() is Locale.UZ
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement accessor**

```python
from starlette.requests import Request
from application.localization.locale import Locale


class CurrentLocaleAccessor:
    def __init__(self, request: Request) -> None:
        self._request = request

    def get_locale(self) -> Locale:
        return Locale.parse(self._request.headers.get("accept-language"))
```

- [ ] **Step 4: Implement provider**

```python
from dishka import Provider, Scope, provide
from fastapi import Request

from application.localization.catalog import MessageCatalog
from application.localization.locale import Locale
from infrastructure.localization.current_locale_accessor import CurrentLocaleAccessor


class LocalizationProvider(Provider):
    @provide(scope=Scope.APP)
    def catalog(self) -> MessageCatalog:
        return MessageCatalog()

    @provide(scope=Scope.REQUEST)
    def locale_accessor(self, request: Request) -> CurrentLocaleAccessor:
        return CurrentLocaleAccessor(request)

    @provide(scope=Scope.REQUEST)
    def locale(self, accessor: CurrentLocaleAccessor) -> Locale:
        return accessor.get_locale()
```

- [ ] **Step 5: Wire into `__init__.py` and `container.py`** (add near `AuthProvider()`).

- [ ] **Step 6: Run full `pytest`, `ruff`, `ty`. Start the app once (`uv run python -c "from di.container import create_container; create_container()"`) to catch a graph error.**

- [ ] **Step 7: Commit** — `feat(i18n): request-scoped Locale and APP-scoped MessageCatalog providers`

---

## Task 4: Frontend forwards the locale

**Files:**
- Modify: `frontend/src/server/backend.ts` (add `locale` to `CallOptions`, set `Accept-Language`)
- Create: `frontend/src/server/locale.ts` (`serverLocale()` — read + validate cookie)
- Modify: `frontend/src/app/api/backend/[...path]/route.ts` (pass locale into both `callBackend` calls)
- Modify: `frontend/src/app/api/backend/proxy.test.ts`
- Test: extend `proxy.test.ts`

**Interfaces:**
- Produces: `serverLocale(): Promise<Locale>` reading `cookies()`, validating with `isLocale`, else `DEFAULT_LOCALE`.
- `callBackend(path, { ..., locale?: string })` → sets `headers["Accept-Language"] = locale` when present.

- [ ] **Step 1: Failing test in `proxy.test.ts`** — assert the upstream fetch is called with `Accept-Language` equal to the `apex_locale` cookie value, and with `uz` when the cookie is missing/invalid. Follow the existing mock style in that file.

- [ ] **Step 2: Run `pnpm test src/app/api/backend/proxy.test.ts`, verify fail.**

- [ ] **Step 3: Implement `serverLocale`**

```typescript
import "server-only";
import { cookies } from "next/headers";
import { DEFAULT_LOCALE, LOCALE_COOKIE, isLocale } from "@/i18n/config";
import type { Locale } from "@/i18n/config";

export async function serverLocale(): Promise<Locale> {
  const value = (await cookies()).get(LOCALE_COOKIE)?.value;
  return isLocale(value) ? value : DEFAULT_LOCALE;
}
```

- [ ] **Step 4: `backend.ts`** — add `locale?: string` to `CallOptions`; `if (locale) headers["Accept-Language"] = locale;`.

- [ ] **Step 5: `route.ts`** — `const locale = await serverLocale();` near `readTokens()`, pass `locale` into both `callBackend(...)` calls.

- [ ] **Step 6: Run `pnpm typecheck && pnpm lint && pnpm test`. Commit** — `feat(i18n): BFF forwards apex_locale as Accept-Language`

---

## Task 5: Error `code` on the base exceptions, catalog wired into the handler

**Files:**
- Modify: `backend/src/domain/errors.py` (add `code` via `__init_subclass__`, `params` on `__init__`)
- Modify: `backend/src/application/errors.py` (same, and keep `EntityNotPersistedError.__init__` working)
- Modify: `backend/src/presentation/errors.py` (`_handle` renders via catalog; `register_error_handlers(app, catalog)`)
- Modify: `backend/src/presentation/app.py` (pass the catalog into `register_error_handlers` — resolve it from the container: `await container.get(MessageCatalog)` at startup, or construct `MessageCatalog()` directly since it is APP-scoped and stateless)
- Modify: `backend/src/application/localization/messages/en.toml` (add `[errors]` entries for every code — start with the ones that have no params, seeded from current messages)
- Test: `backend/tests/application/localization/test_error_codes.py`, `backend/tests/api/test_error_localization.py`

**Interfaces:**
- Consumes: `MessageCatalog`, `Locale`.
- Produces: `DomainError.code: ClassVar[str]`, `ApplicationError.code: ClassVar[str]`, both `.params: dict[str, object]`.
- Produces: `register_error_handlers(app: FastAPI, catalog: MessageCatalog) -> None`.

- [ ] **Step 1: Failing test — codes exist and are unique**

```python
from domain.errors import DomainError
from application.errors import ApplicationError

def _all_subclasses(base):
    for c in base.__subclasses__():
        yield c
        yield from _all_subclasses(c)

def test_every_error_has_a_snake_case_code():
    for cls in [*_all_subclasses(DomainError), *_all_subclasses(ApplicationError)]:
        assert cls.code and cls.code.islower()

def test_codes_are_unique():
    codes = [c.code for c in [*_all_subclasses(DomainError), *_all_subclasses(ApplicationError)]]
    assert len(codes) == len(set(codes))
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement on `DomainError`**

```python
from typing import ClassVar


def _snake(name: str) -> str:
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i and not name[i - 1].isupper():
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


class DomainError(Exception):
    code: ClassVar[str] = "domain"

    def __init_subclass__(cls, **kw: object) -> None:
        super().__init_subclass__(**kw)
        cls.code = _snake(cls.__name__.removesuffix("Error"))

    def __init__(self, message: str = "", /, **params: object) -> None:
        super().__init__(message)
        self.params: dict[str, object] = params
```

Mirror on `ApplicationError`. Keep `EntityNotPersistedError.__init__` (call `super().__init__(f"...", model_name=..., entity_id=...)`).

- [ ] **Step 4: `_handle`**

```python
async def _handle(request: Request, exc: Exception) -> JSONResponse:
    status = _status_for(exc)
    locale = Locale.parse(request.headers.get("accept-language"))
    code = getattr(exc, "code", None)
    detail = (
        _catalog.render(locale, "errors", code, **getattr(exc, "params", {}))
        if code
        else None
    )
    detail = detail or str(exc) or exc.__class__.__name__
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(status_code=status, content={"detail": detail}, headers=headers)
```

Set module global `_catalog` in `register_error_handlers(app, catalog)`.

- [ ] **Step 5: API test** — hit an endpoint that raises a known error (e.g. `GET` a missing invoice PDF) with `Accept-Language: ru` after adding its `ru` entry; assert `detail` is the Russian text. Also assert an un-catalogued code still returns the English exception message.

- [ ] **Step 6: Seed `en.toml [errors]`** for the no-param codes, text copied from the current exception messages / docstrings.

- [ ] **Step 7: Full `pytest`, `ruff`, `ty`. Commit** — `feat(i18n): route error detail through the message catalog`

---

## Task 6: Migrate interpolated error raise sites to params (phased)

**Files (per phase, one commit each):**
- `backend/src/application/services/accessory_line_writer.py`, `document_lines.py`, `removal_scanning.py`, `removal_posting.py`, ... (all ~57 f-string raise sites — `grep -rn "raise [A-Z][A-Za-z]*Error(f" backend/src`)
- Matching `[errors]` keys in all three TOML files.
- Existing tests that assert on message substrings — update to assert on the localized output or the `.params`.

**Interfaces:**
- Consumes: `DomainError.__init__(message, /, **params)` (Task 5).

Phases (each is: change raise sites → add `en`/`ru`/`uz` keys → run `pytest -k <area>` → `ruff`/`ty` → commit):

- [ ] **Phase 6a: catalog & scanning** — `document_lines.py`, `removal_scanning.py`, `accessory_line_writer.py`
- [ ] **Phase 6b: receipts** — goods receipt / purchase order confirm errors (`OverReceiptError`, `UnpricedUnitError`, `UnpricedOrderLineError`, `DuplicateImeiError`, `DuplicateScanError`)
- [ ] **Phase 6c: invoices** — `UnitNotSellableError`, `WrongLocationError`, `InsufficientStockError`, `PriceNotSetError`, `EmptyInvoiceError`
- [ ] **Phase 6d: credit** — `CreditTermsError`, `AnonymousDebtError`, `NotACreditSaleError`, `OverpaymentError`, `PaymentAlreadyReversedError`
- [ ] **Phase 6e: removals & counts** — `UnitNotRemovableError`, `UnitNotFromSupplierError`, `EmptyDocumentError`, `CountNotClosedError`, `CountAlreadyClosedError`
- [ ] **Phase 6f: remaining application errors** — `NotFoundError`, `DuplicateImeiError` (app layer), `DuplicateSkuError`, `DuplicateBarcodeError`, `DuplicateNameError`, `InvalidLogoError`, etc.

Example raise-site change (6c, `accessory_line_writer.py:68`):

```python
raise InsufficientStockError(
    f"this store holds {on_hand} of {product.sku}, and the invoice would sell {wanted}",
    on_hand=on_hand, sku=product.sku, wanted=wanted, invoice_number=invoice.number,
)
```

`en.toml`:
```toml
insufficient_stock = "This location holds {on_hand} of {sku}; {invoice_number} would sell {wanted}. No partial fulfilment (FR-4.7)."
```

- [ ] **After the last phase: add the catalog-parity test** in `backend/tests/application/localization/test_catalog.py`:

```python
def test_all_locales_have_the_same_keys():
    cat = MessageCatalog()
    for table in ("errors", "documents"):
        en = cat.keys(table)
        for locale in (Locale.RU, Locale.UZ):
            assert cat._data[locale].get(table, {}).keys() >= en, (
                f"{locale} missing {table} keys: {en - cat._data[locale].get(table, {}).keys()}"
            )
```

- [ ] **And the code-coverage test:** every `code` on a `DomainError`/`ApplicationError` subclass that is user-facing (status < 500) has an `en.toml [errors]` entry.

---

## Task 7: Locale-aware document renderers

**Files:**
- Modify: `backend/src/application/ports/documents.py` (add `locale: Locale` to each `render` signature)
- Modify: `backend/src/infrastructure/documents/page.py` (`DocumentPage.__init__` takes `locale` + `MessageCatalog`; replace literals with `self._t(...)`)
- Modify: `backend/src/infrastructure/documents/invoice_pdf.py`, `purchase_order_pdf.py`, `supplier_return_pdf.py`, `month_end_pdf.py` (drop `_HEADERS` string literals, `"Invoice"`, etc.; pull from catalog)
- Modify: `backend/src/infrastructure/documents/__init__.py` if constructor exports change
- Modify: `backend/src/di/providers/documents.py` (`DocumentPageFactory` takes `MessageCatalog`; renderers unchanged otherwise)
- Modify: `backend/src/application/queries/get_sales_invoice_pdf.py`, `get_purchase_order_pdf.py`, `get_supplier_return_pdf.py`, `get_month_end_report_pdf.py` (add `locale: Locale` constructor param, pass to `renderer.render`)
- Modify: `backend/src/application/localization/messages/*.toml` (`[documents]` keys)
- Test: `backend/tests/api/test_invoice_pdf.py` (or wherever the PDF text assertions live) — per-locale heading assertion using `pdf_text`

**Interfaces:**
- Consumes: `Locale`, `MessageCatalog`.
- Produces: `DocumentPageFactory.__init__(self, font_path, catalog)`, `DocumentPageFactory.page(self, locale: Locale) -> DocumentPage`.
- Produces: `InvoiceRenderer.render(self, invoice, letterhead, descriptions, locale)` (and the other three renderers similarly).

`[documents]` keys (seed all three TOML files; `ru`/`uz` translated in Task 8):

```toml
[documents]
invoice_title = "Invoice"
purchase_order_title = "Purchase Order"
supplier_return_title = "Supplier Return"
col_item = "Item"
col_qty = "Qty"
col_price = "Price"
col_total = "Total"
confirmed_at = "Confirmed {timestamp}"
total_for_currency = "Total ({currency})  {amount}"
cancelled = "CANCELLED: {reason}"
no_reason_given = "no reason given"
detail_supplier = "Supplier"
detail_location = "Location"
detail_reason = "Reason"
# month-end keys — enumerate from month_end_pdf.py while editing it
```

- [ ] **Step 1: Failing test** — render the invoice PDF via the API with `Accept-Language: ru`, assert `pdf_text(body)` contains the `ru` value of `invoice_title` (add a temporary `ru` value first). Confirm the `en` path still says "Invoice".

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: `DocumentPage`** — add `def __init__(self, catalog, locale, font=None)`; add `def _t(self, table, key, **p): return self._catalog.render(self._locale, table, key, **p) or key`. Replace `"Invoice"`/header literals in `heading`, `table` callers, `subtotals`, `cancellation`. `invoice_pdf.py` passes `page.heading(invoice, self._t("documents","invoice_title"))` — or move the title lookup into `heading` keyed by document type. Simplest: renderer passes the already-resolved title string, `DocumentPage` resolves only its own fixed words (`confirmed_at`, `total_for_currency`, `cancelled`, `no_reason_given`).

- [ ] **Step 4: Each renderer** — replace `_HEADERS = ("Item", ...)` with a method building the tuple from `self._page ... _t(...)` at render time; accept and thread `locale`.

- [ ] **Step 5: Ports + query handlers + provider** — add the `locale` param through the chain. Query handler gets `Locale` injected (provider from Task 3), passes to `renderer.render`.

- [ ] **Step 6: Full `pytest`, `ruff`, `ty`. Commit** — `feat(i18n): locale-aware PDF document rendering`

---

## Task 8: Cyrillic font + fill ru/uz translations

**Files:**
- Create: `backend/src/infrastructure/documents/fonts/DejaVuSans.ttf` (download; ~750 KB; SIL/Bitstream licence — add a `LICENSE` note file next to it)
- Modify: `backend/src/infrastructure/config.py` (`pdf_font_path` default points at the bundled file if it exists)
- Modify: `backend/pyproject.toml` (ship the `.ttf` in the package)
- Modify: `backend/src/application/localization/messages/ru.toml`, `uz.toml` (real translations for every `[errors]` and `[documents]` key)
- Modify: `backend/.env.example` (document `APEXWMS_PDF_FONT_PATH`)
- Test: `backend/tests/api/test_invoice_pdf.py` — with the bundled font, a Cyrillic product name / the `ru` heading round-trips through `pdf_text` (no `?`).

- [ ] **Step 1: Failing test** — assert the `ru` invoice PDF contains the Cyrillic heading text intact.
- [ ] **Step 2: Add the font file, point the config default at it.**
- [ ] **Step 3: Verify the parity test from Task 6 passes** once `ru.toml`/`uz.toml` are filled.
- [ ] **Step 4: Full `pytest`, `ruff`, `ty`. Commit** — `feat(i18n): bundle Cyrillic PDF font, add ru/uz message translations`

---

## Task 9: Frontend string audit

**Files:**
- Any `frontend/src/**/*.tsx` with a hardcoded user-facing string not going through `useTranslations` / `getTranslations`.
- Matching entries in `frontend/messages/{en,ru,uz}.json`.

- [ ] **Step 1:** `grep` for literal strings in JSX text nodes and common props (`label=`, `placeholder=`, `title=`, `description=`) across `frontend/src/app` and `frontend/src/components`. Skip test files and `lib/`.
- [ ] **Step 2:** For each real miss, add a message key and replace with a translation call. Keep changes mechanical, one area per commit.
- [ ] **Step 3:** `pnpm typecheck && pnpm lint && pnpm test` after each area. Commit — `i18n(frontend): translate <area> strings`.

---

## Self-Review

- **Spec coverage:** locale plumbing (Tasks 1,3,4), catalog (Task 2), error codes+params (Tasks 5,6), presentation mapping (Task 5), document rendering (Task 7), font (Task 8), UI audit (Task 9), parity test (Task 6). Pydantic 422 explicitly out of scope per spec. Covered.
- **Placeholders:** none; the per-phase raise-site list in Task 6 is enumerable by the given `grep`, with one worked example.
- **Type consistency:** `Locale.parse` used in both `_handle` (Task 5) and the accessor (Task 3) — same signature. `MessageCatalog.render` positional-only `locale, table, key` then `**params` — used consistently in Tasks 5, 7. `DocumentPageFactory.page(locale)` — Task 7 only.
