---
paths:
  - "docs/architecture/**/*.md"
---

# `docs/architecture/` explains how the system is built, not what the business needs

`docs/prd.md` is the spec: functional requirements, business rules, the
delivery plan. `docs/architecture/` is a different document with a
different job: given that the PRD says X, here is how the codebase
implements it — layers, file locations, patterns, invariants, what a test
enforces. Confusing the two turns the architecture docs into a second,
drifting copy of the PRD.

## Rules

1. **Cite a PRD section, don't restate its rule.** `(PRD §4.5b)` next to a
   sentence about how the code is shaped is fine. A paragraph explaining
   *why the business* needs that rule (the scenario, the money at stake,
   the person affected) belongs in the PRD, not here — if it's worth
   saying, it's worth saying once, and the PRD is the source of truth for
   it.
2. **No delivery status.** Which milestone is current, what's done, what's
   deferred — that's `docs/prd.md` §10, one source of truth. An
   architecture doc may say "as of M4" to date a fact, but must not carry
   its own roadmap, milestone table, or "current state" section that
   duplicates §10. `milestones.md` exists only as a one-line pointer for
   this reason.
3. **No FR-numbered bullet lists.** A string of `FR-x.x` citations reading
   like a condensed spec excerpt is a sign the file has become a PRD
   summary. Name the class/function/test that implements the rule instead;
   the FR number is a footnote, not the point of the sentence.
4. **The litmus test:** if a paragraph would still make complete sense with
   every class name, file path, and test name stripped out of it, it isn't
   an architecture fact — it's a business rule that migrated here by
   accident. Move it to the PRD (or delete it if the PRD already has it)
   and leave a citation.
5. **Don't start a new file per milestone or feature.** A new milestone
   almost always extends a concept that already has a file: a new document
   type is still `documents.md`, a new entry type on the ledgers is still
   `ledgers.md`. Add a section or a bullet there instead of spinning up
   `sales.md`/`m5.md`/etc. Start a new file only when a genuinely new
   architectural *mechanism* shows up, one with no existing home — the way
   `tenant-resolution.md` earned its own file because tenant resolution
   grew into a mechanism worth explaining on its own, not because a
   milestone happened to introduce it. If you're unsure, extend the
   existing file; a file that's grown too long to read is a much easier
   problem to notice and fix than a folder that's grown too fragmented to
   navigate.

## What does belong here

Layer boundaries and what each owns, module/file locations, DI wiring
patterns, repository/service shapes, which test or type-check enforces an
invariant, and *technical* trade-offs — why a design took the shape it did
in code (e.g. "a `NewType` wrapper because `ty check` is the only thing
that can catch a wrong-session bug"). That reasoning is about the
implementation, not the business, and it has nowhere else to live.
