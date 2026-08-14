# Delivery milestones

Milestone scope, order, and demo criteria live in one place: `docs/prd.md`
§10. Don't duplicate that table here — check it before assuming a feature
belongs in the current milestone.

**Current state: M4** — see [ledgers.md](ledgers.md) for M3 (the ledgers)
and [documents.md](documents.md) for M4 (purchase orders, goods receipts).
`LedgerPoster` has its first real caller in M4: stock enters over HTTP,
through a document, and nothing else.
