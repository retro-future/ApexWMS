# Document and error localization

## Goal

One rule for language, applied consistently: every piece of text a user reads
follows the language they picked in the app. That language is the `apex_locale`
cookie (`uz` default, also `ru`, `en`), already used by next-intl for UI chrome.

Three surfaces need work:

1. **UI chrome** (buttons, menus, labels) - already translated through
   next-intl. Only an audit for missed strings.
2. **Warnings and errors** - the backend sends English prose in the `detail`
   field today. Make it send localized text for the request's locale.
3. **Printed documents** (Sales Invoice, Purchase Order, Supplier Return,
   Month-End Report) - rendered server-side with English literals baked in.
   Make the renderer take a locale and pull its text from a catalog.

Approach A was chosen for errors: the backend owns the message catalog and
formats the final string. The frontend keeps showing `detail` unchanged. The
document renderer needs a backend catalog anyway, so both surfaces share one
mechanism.

## Out of scope

- Translating catalog data: product names, supplier names, location names,
  cancellation reasons typed by a user. These print and display as stored, in
  whatever language the store entered them. Variant A accepts this.
- Per-document language choice (a `ru` invoice while the UI stays `uz`). That
  was variant B and was rejected.
- Pydantic 422 request-validation messages. There are hundreds and they are
  rarely user-facing. They stay English. A later pass may map the few common
  ones.

## Non-negotiable constraints

- `domain/` keeps zero imports from outside itself. The message catalog and
  the locale type live in `application/` and `infrastructure/`, never in
  `domain/`.
- Providers stay dumb (`.claude/rules/backend/providers.md`). Locale
  resolution is a small `infrastructure/` accessor class, injected, not an
  `if` in a `@provide` method.
- PDF re-rendering stays byte-identical for a given input
  (`DocumentPage.start` pins the creation date). Locale is part of the input,
  so a locale change legitimately changes the bytes; nothing else may.
- `uv run ty check` stays green. The locale value is a `StrEnum` or `NewType`,
  not a bare `str` floating through signatures.

## Locale plumbing

### Frontend: forward the cookie

The BFF proxy (`frontend/src/app/api/backend/[...path]/route.ts`) reads the
`apex_locale` cookie and passes it to `callBackend`, which sets an
`Accept-Language` header on the server-to-server fetch.

- `frontend/src/server/backend.ts`: add an optional `locale` field to
  `CallOptions`; when set, add `headers["Accept-Language"] = locale`.
- `route.ts`: read `cookies().get(LOCALE_COOKIE)?.value`, validate with
  `isLocale`, pass it (or `DEFAULT_LOCALE`) into both `callBackend` calls.
- `frontend/src/server/backend.ts` is also called directly by server
  components (`backendData`). Those call sites pass the locale the same way.
  Add a small `serverLocale()` helper in `frontend/src/server/` that reads and
  validates the cookie, so every server-side backend call has one source.
- Update `frontend/src/app/api/backend/proxy.test.ts` for the new header.

### Backend: request-scoped locale

- New `application/localization/locale.py`: `class Locale(StrEnum)` with
  `UZ = "uz"`, `RU = "ru"`, `EN = "en"`, and `DEFAULT = UZ`. A
  `Locale.parse(header: str | None) -> Locale` classmethod does a forgiving
  parse of the `Accept-Language` value (exact match on the first tag, strip
  any `-Region` and `;q=` weight, fall back to `DEFAULT`).
- New `infrastructure/localization/current_locale_accessor.py`:
  `CurrentLocaleAccessor` takes the `Request`, exposes
  `get_locale() -> Locale` reading `request.headers.get("accept-language")`.
  Mirrors `CurrentUserAccessor`'s shape.
- New `di/providers/localization.py`: `LocalizationProvider` with a
  `Scope.REQUEST` provide for `CurrentLocaleAccessor` and one for `Locale`
  (calls `accessor.get_locale()`). Register it in the container assembly next
  to `AuthProvider`.
- The APP-scoped catalog objects (below) are provided here too.

## Message catalog

### Storage

`backend/src/application/localization/messages/` holds three files, one per
locale: `en.toml`, `ru.toml`, `uz.toml`. TOML, because the values are short
strings with named placeholders and translators should not meet JSON quoting.

Two top-level tables per file:

```toml
[errors]
duplicate_imei = "This store already holds a handset with IMEI {imei} ({status} at {location})."
insufficient_stock = "This location holds {on_hand} of {sku}; the invoice would sell {wanted}. No partial fulfilment (FR-4.7)."
# ... one key per error code

[documents]
invoice_title = "Invoice"
col_item = "Item"
col_qty = "Qty"
col_price = "Price"
col_total = "Total"
confirmed_at = "Confirmed {timestamp}"
total_for_currency = "Total ({currency})  {amount}"
cancelled = "CANCELLED: {reason}"
no_reason_given = "no reason given"
# ... purchase order, supplier return, month-end keys
```

Placeholders are `str.format` style. Keys are flat within a table.

### Loader

`application/localization/catalog.py`:

- `class MessageCatalog` - constructed once at APP scope. Loads all three
  TOML files at startup into `dict[Locale, dict[str, dict[str, str]]]`.
- `render(locale: Locale, table: str, key: str, /, **params: object) -> str | None`
  - looks up `[table][key]` for `locale`, falls back to `Locale.EN`, then
    `None`. Applies `.format(**params)`; a `KeyError` from a missing
    placeholder is caught and logged, returning the unformatted template
    rather than raising (a slightly wrong message beats a 500, same principle
    as the PDF font fallback).
- A `pytest` test asserts every key present in `en.toml` is present in
  `ru.toml` and `uz.toml`, and that no `[errors]` key is missing a catalog
  entry for a code that exists in the code (see next section). This test is
  the guard against a half-translated release.

## Errors: codes and params

### Error code

Every `DomainError` and `ApplicationError` subclass gets a stable `code`
string. Derive it once on the base classes from the class name
(`DuplicateImeiError` -> `duplicate_imei`), as a class attribute computed in
`__init_subclass__`, so no raise site changes just to get a code.

```python
class DomainError(Exception):
    code: ClassVar[str]

    def __init_subclass__(cls, **kw: object) -> None:
        super().__init_subclass__(**kw)
        cls.code = _snake_case(cls.__name__.removesuffix("Error"))
```

Same on `ApplicationError`. `EntityNotPersistedError` and
`ProvisioningFailedError` are internal (500s); they get a code but no catalog
entry is required and the fallback path covers them.

### Error params

The base `__init__` accepts an optional keyword bag and stores it:

```python
    def __init__(self, message: str = "", /, **params: object) -> None:
        super().__init__(message)
        self.params: dict[str, object] = params
```

The ~57 raise sites that build an f-string message today are migrated to pass
structured params **and** keep a plain-English fallback message:

```python
raise DuplicateImeiError(
    f"this store already holds a handset with IMEI {imei}",
    imei=str(imei), status=existing.status.value, location=existing.location_name,
)
```

Raise sites with no interpolation (the majority) are left untouched; their
catalog template is a static sentence.

Migration is phased by feature area (auth, catalog, receipts, invoices,
credit, removals, counts) so each phase is a reviewable diff with its own
tests. The English catalog for each phase is seeded from the existing
messages.

### Presentation mapping

`presentation/errors.py` `_handle` becomes:

```python
async def _handle(request: Request, exc: Exception) -> JSONResponse:
    status = _status_for(exc)
    locale = Locale.parse(request.headers.get("accept-language"))
    code = getattr(exc, "code", None)
    detail = None
    if code is not None:
        detail = _catalog.render(locale, "errors", code, **getattr(exc, "params", {}))
    detail = detail or str(exc) or exc.__class__.__name__
    ...
```

`_catalog` is module-level, set by `register_error_handlers(app, catalog)`.
The exception handler runs outside Dishka's request scope, so the catalog is
passed in at registration, not injected.

Fallback chain: locale template -> English template -> the exception's own
message string -> class name. A code with no catalog entry still produces the
current English behavior.

## Documents: locale-aware rendering

### Threading the locale in

The four PDF query handlers gain a `Locale` constructor parameter (resolved by
`LocalizationProvider`):

- `application/queries/get_sales_invoice_pdf.py`
- `application/queries/get_purchase_order_pdf.py`
- `application/queries/get_supplier_return_pdf.py`
- `application/queries/get_month_end_report_pdf.py`

Each passes `locale` into `renderer.render(...)`. The renderer port signatures
in `application/ports/documents.py` gain a `locale: Locale` parameter.

### Renderer text

`DocumentPage` and each `Pdf*Renderer` stop holding string literals. Two
options considered:

- **A pass-through dict**: the query handler resolves every needed string from
  the catalog and hands the renderer a `dict[str, str]`. Keeps `DocumentPage`
  free of any catalog dependency. Verbose at the call site.
- **Inject the catalog** (recommended): `DocumentPageFactory` takes the
  `MessageCatalog` at APP scope; `DocumentPage` is created with a bound
  `locale` and calls `self._t("documents", "col_item")` internally. The
  renderer reads like prose and the catalog stays one object.

Recommended: inject the catalog. `_HEADERS`, `_WIDTHS` stay as structure;
the header text comes from `self._t(...)` at render time. `page.heading`,
`page.subtotals`, `page.cancellation` take their fixed words from the catalog.

Month-end report (`month_end_pdf.py`) has the most literals; it gets its own
block of `[documents]` keys.

### Numbers, dates, currency

Unchanged. `Money.format()` stays as is. Dates stay ISO (`%Y-%m-%d %H:%M %Z`).
Localizing number grouping and date order is a separate, later decision and
not part of variant A.

### Cyrillic font

The built-in Helvetica cannot draw Cyrillic; today an unencodable character
becomes `?`. A `ru` document is unreadable without a Unicode font.

Decision to confirm at review: bundle a Unicode TTF (DejaVuSans, ~750 KB, or
Noto Sans) in `backend/src/infrastructure/documents/fonts/` and default
`APEXWMS_PDF_FONT_PATH` to it. Without this step, `ru` and Cyrillic-entered
`uz` documents still print `?` and the feature is not really delivered.

If font bundling is deferred, this spec still ships, but the release notes
must state that `ru` documents need `APEXWMS_PDF_FONT_PATH` set to a
Cyrillic-capable font.

## Testing

Backend:

- `application/localization`: catalog loader unit tests (lookup, English
  fallback, missing-placeholder behavior); the key-parity test across the
  three TOML files; a test that every error `code` in the codebase has an
  `[errors]` entry.
- `Locale.parse`: table test over `Accept-Language` values
  (`"ru"`, `"ru-RU"`, `"en-US,en;q=0.9"`, `""`, `None`, `"fr"`).
- `presentation/errors.py`: raise a representative error under
  `Accept-Language: ru` and assert `detail` is the Russian template with
  params filled; assert an un-catalogued code falls back to English.
- `tests/api/pdf_helpers.py`: extend `pdf_text` usage - one test per locale
  asserting the invoice PDF contains the translated heading and column
  labels, and (with the bundled font) a Cyrillic string round-trips.

Frontend:

- `proxy.test.ts`: the `Accept-Language` header is forwarded from the cookie,
  and defaults when the cookie is absent or invalid.
- Existing vitest suite stays green; the audit adds no new components.

## Rollout order

1. Locale plumbing: BFF header, backend `Locale` + accessor + provider. No
   user-visible change yet.
2. Catalog loader, TOML files (English only), parity test.
3. `presentation/errors.py` wired to the catalog; error `code` on the base
   classes. Still English-only output, but now routed through the catalog.
4. Error param migration, phase by feature area.
5. Document renderer catalog + locale threading through the four PDF handlers.
6. Cyrillic font bundling (or the documented env-var fallback).
7. Fill `ru.toml` and `uz.toml`.
8. Frontend audit for missed UI strings.
