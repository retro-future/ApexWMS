---
paths:
  - "backend/src/application/commands/**/*.py"
  - "backend/src/application/queries/**/*.py"
---

# A command/query module defines its message and its handler — nothing else

A file in `application/commands/`/`application/queries/` exists for **one**
CQRS operation: one `Command`/`Query`, one `IRequestHandler`. It is not a
place to accumulate the helper functions that operation happens to need.

## Rules

1. **No module-level `_private_function`.** If logic is worth naming, it is
   worth a home outside the one-operation module — see below for where.
2. **Logic reusable across more than one handler** (shared parsing,
   formatting, a data-loading helper several sibling commands need) belongs
   in `application/services/` **as its own DI-injected class**, or on the
   port/service that already owns the concept it touches. Prefer the latter
   when one already exists: `TokenService.parse_opaque` (below) extends the
   port that already owns opaque-token construction and hashing, rather than
   inventing a new home next to it. A bare module-level function in
   `application/services/` is not acceptable even as an interim step —
   `application/services/device_unit_loader.py`'s `DeviceUnitLoader` (a
   constructor-injected class with one `load()` method, registered in
   `di/providers/services.py` and taken as a handler constructor parameter,
   same shape as `DeviceUnitRepricer`/`ProductRepricer`) is the pattern
   every service in that package follows.
3. **Logic used by exactly one handler**, that reads or mutates that
   handler's own request or the entities it just fetched, stays a **private
   method on the handler class**. This is not the same violation as rule 1 —
   a method on the one class that owns the operation is not module-level,
   and does not need to move anywhere.
4. **A helper reused by more than one file is the same problem even when
   it's public.** A public module-level function that two or three sibling
   commands import doesn't trip rule 1, but it's still living in one
   operation's module for the convenience of others — move it to
   `application/services/` as a DI-injected class, same as rule 2.

## Example: what this looks like in practice

`refresh_tokens.py` and `accept_invite.py` used to each define an identical
module-level `_parse(token) -> tuple[UUID, str]`, splitting the opaque
`"{id}.{secret}"` wire format and raising their own error on malformed
input — a duplicated helper hiding as a private function in two use-case
modules. `TokenService` (`application/ports/security.py`) already owns that
format's construction (`issue_refresh`, `new_opaque_secret`) and hashing
(`hash_opaque`), so parsing moved onto the same port:

```python
class TokenService(Protocol):
    def parse_opaque(self, token: str) -> tuple[UUID, str] | None:
        """Split an opaque "{id}.{secret}" token; None if malformed."""
        ...
```

`parse_opaque` returns `None` rather than raising, because the two callers
want *different* exceptions (`InvalidTokenError` vs `InvitationError`) —
deciding which one is the handler's business rule to own
(`.claude/rules/backend/exception-handling.md`), not the token service's.

By contrast, `AcceptInviteHandler._grant_app_role`/`_join_store` and
`_validate` stay exactly where they are: each reads and mutates state that
only `AcceptInviteHandler` itself has (the invitation it just validated,
the user it just created), and nothing else in the codebase needs them.

See also `.claude/rules/backend/cqrs-response-models.md` for the companion
rule about where a handler's *response* payload class belongs.
