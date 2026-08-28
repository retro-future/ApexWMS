---
paths:
  - "backend/src/di/providers/mappers.py"
  - "backend/src/di/providers/tenant_repository.py"
  - "backend/src/di/providers/master_repository.py"
---

# The mapper and repository providers are already generic

`MapperProvider` and `TenantRepositoryProvider` (and its master sibling) are
written once and take no per-aggregate change. See also `providers.md` for
the general "providers stay dumb" rules that also apply here.

## Rules

1. **Converting an aggregate never edits these files.** The entire DI step
   for a new aggregate is: write the mapper, add its instance to
   `COMMON_MAPPERS` in `infrastructure/persistence/mappers/__init__.py`. If a
   conversion seems to need a new `@provide` method, the mapper or the model
   is missing something (usually the `model` attribute), not the provider.

2. **Do not add per-aggregate factories.** One generic factory per database
   was a deliberate trade against the "four repositories forever" problem. A
   per-aggregate `@provide` reopens it.

## Known limit

The entity/model pairing in `MapperRegistry` is a runtime dict lookup, not
something `ty` checks. `TenantDbRepository[Location, SupplierModel]` would
resolve and hand back a `SupplierMapper`; only a truly unmapped model fails,
with `UnmappedModelError`. See `di/providers/mappers.py`'s docstring.
