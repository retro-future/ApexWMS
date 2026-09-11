# W9 — The exchange rate and the money picture

**Version:** 0.1 (scope, branches B1–B7)
**Status:** B1, B1b, B2, B3, B4, B7 done; B5 and B6 ship with W5
**Last updated:** 2026-09-11

---

## 0. What this file is

This workstream **reopens a decision `prdv2.md` lists as fixed ground**: "no base
currency, no exchange rate, two totals rather than one combined bottom line (§4.5)".
That section requires a feature needing one of those to reopen it explicitly, in its own
PRD, with the reasoning written down. This is that file.

The reasoning is in §1. The short version: §4.5 is right that a converted amount must
never be *stored as a fact*, and wrong that a *report* may refuse to convert. V1 got the
first half and shipped the second half as if it were the same rule. The result is a
system that records every number correctly and cannot answer "how much did I make".

Nothing here proposes converting inside either ledger. `Money`, `CurrencyTotals`, the
minor-unit integers and the ban on floats all stay exactly as they are.

---

## 1. The hole

One phone, start to finish, in the system as it ships today.

**Intake.** A supplier delivers an iPhone. The receipt records `acquisition_cost` of
$300, in the product's currency. The store actually handed over 3 750 000 som. That
figure exists nowhere.

**Sale.** The shelf price is $350. The customer pays in som. The seller multiplies 350
by the store's rate of 12 000 in their head, says 4 200 000 som, and takes it.
`InvoicePoster` books `SALE_REVENUE` of $350 and `COGS` of -$300
(`application/services/invoice_posting.py`). The som figure is either not recorded at
all, or, with `tenant_settings.runs_till` on, written as a `TENDER_RECEIVED` row that no
report reads.

**Month end.** `MonthEndReporter` returns revenue $350, cost of goods -$300, margin $50
(`application/services/month_end.py`). The owner asks where the money is. The drawer
holds 4 200 000 som. The report holds $50. **There is not one number in the system that
connects them.**

Three places where that costs real money:

**The seller's own rate.** Sold at 11 500 instead of 12 000, the customer hands over
4 025 000 instead of 4 200 000, and 175 000 som goes into a pocket or into an unrecorded
discount. The report reads $50 margin in both cases, because it only ever looks at the
dollar price list. Undetectable.

**The instalment markup.** The same phone on store credit. The seller writes a debt of
5 000 000 som. At the day's rate the phone was 4 200 000. The 800 000 difference, around
$66, is the store's earnings on the instalment and is larger than the margin on the sale
itself. `SalesInvoice.debt` is som and is deliberately unrelated to the line prices
(`domain/entities/sales_invoice.py`), so that 800 000 lands in `DebtMovement.booked` and
in no income figure anywhere. A store selling half its phones on credit earns roughly
three times what the report shows and does not know it.

**The used-handset buy.** The intake clerk types "$250" and hands over 3 500 000 som. At
12 000 that is $291. `DeviceUnit` carries both numbers, `acquisition_cost` in the
product's currency and `cash_paid_minor` in som, and never compares them
(`domain/entities/device_unit.py`). Inventory carries whatever was typed.

---

## 2. What §4.5 got right, and what it got wrong

**Right, and staying:** an amount is a fact in the currency it happened in. 4 200 000 som
is 4 200 000 som, not $350. `Money` with per-currency exponents, `CurrencyTotals` that
cannot physically add two currencies, the ban on floats and on implicit conversion in the
domain, all of it stays. This is the part that makes the highest-risk mistake in prd.md
§11's table structurally impossible, and it is worth what it cost.

**Wrong:** that a report may decline to convert. A report that shows two unconnected
columns is not a careful report, it is one that does not answer the question. The owner
converts anyway, mentally, at whatever rate comes to mind, and their figure disagrees
with the system's. The rule to replace it:

> Never store a converted amount as a fact. Always convert in a report, at a rate that
> was recorded when the transaction happened, and print the rate on the report.

---

## 3. The seven holes, named

| # | Hole | Where it lives today |
|---|---|---|
| 1 | The rate a sale was struck at is never recorded, so currency gain and loss does not exist as a concept | nothing in `src/` mentions a rate except comments saying there is none |
| 2 | The instalment markup is not income anywhere | `domain/entities/sales_invoice.py` (`debt` is som and unrelated to the lines), `application/services/month_end.py` (`DebtMovement`) |
| 3 | A used-handset buy's dollar valuation and its som payout are never cross-checked | `domain/entities/device_unit.py`, `application/services/receipt_posting.py` |
| 4 | `TENDER_RECEIVED` and `TENDER_PAID` are written and read by no report | `domain/enums/transaction_type.py`; absent from every file under `application/models`, `application/dtos`, `persistence/tenant/queries` |
| 5 | The till has no opening balance, no cash accounts, no shift close | prd.md §1.3 deferred it, prdv2 W5 owns it |
| 6 | Expenses (rent, wages, an owner's draw) do not exist in the system at all | no entity, no category in `TransactionType` |
| 7 | Supplier debt does not exist: receiving books `PURCHASE` and tracks no balance | `application/services/receipt_posting.py`; prdv2 W5 owns it |

Holes 5 and 7 already belong to **W5 (supplier debt, cash drawer and shifts)**. This file
does not duplicate them; it states what W5 needs from W9 and vice versa.

---

## 4. Branch sequence

Each branch ships on its own and leaves the system usable.

| # | Branch | Closes | Blocked on |
|---|---|---|---|
| **B1** | Rate of the day, and the som figure on every counter sale | 1 (recording half), 4 (partly) | done |
| **B1b** | One tender row per currency on a counter sale | a doubled figure nobody caps | done |
| **B2** | A used-handset buy states both its dollar valuation and its som payout | 3 | done |
| **B3** | The month-end report read in som, at the rate of each day | 4, and the reporting half of 1 | done |
| **B4** | The instalment markup as its own income line, split out of the rate gain | 2 | done |
| **B5** | Cash accounts, opening balances, expenses, shift close | 5, 6 | owner Q7, Q8; ships with W5 |
| **B6** | Supplier debt | 7 | ships with W5 |
| **B7** | Currency gain and loss in the report | what is left of 1 | done |

B1 does not fix the accounting. It stops losing data. A month of B1 in production is a
month of paired figures (dollar price, som taken, official rate) that B7 needs and that
nobody can reconstruct after the fact.

### B1, in one paragraph

An append-only `exchange_rates` table holding two kinds of rate, `SALE` and `BUYBACK`,
in som per dollar, set by an owner or a manager from a card on the dashboard. A confirmed
sale snapshots the rate in force by pointing at its row. The tender field comes off
`runs_till` and is shown on every store's confirm dialog, still optional, with a hint
showing what the dollar total works out to at the day's rate. No report changes by one
figure: `MonthEndReporter._figures` lists its categories by name and `TENDER_*` is not
among them.

### What B1b, B2 and B3 settled

- **A counter sale takes one tender row per currency.** Nothing caps a tender, so a
  second row in a currency already recorded silently doubles what the sale took.
  Half in dollars and half in som stays legal, because that is two true facts.
  Correcting a figure is a reversal and a fresh row, the mechanism payments already
  had.
- **A trade-in cannot be confirmed without the som it paid out**, and it snapshots the
  buying rate the same way a sale snapshots the selling one. A supplier receipt is
  untouched. `TENDER_PAID` is now written for every store, not only one with
  `runs_till` on, for B1's reason: the figure is unrecoverable afterwards.
- **B3 went wider than this file first planned.** It does not only caption the report,
  it converts: every dollar figure is read in som at the selling rate in force on the
  day it happened, in a block of its own beside the untouched per-currency figures. A
  day the log has no rate for takes the most recent earlier one; a day before the log
  starts takes the earliest rate ever quoted, and the report says so. That takes the
  reporting half of hole 1 off B7, which is now the currency gain and loss line alone.
- **What B3 is not.** The som block is a conversion, printed as one. It is not what
  crossed the counter, and the caption on screen and on the PDF says exactly that.
- **A tender is capped only where a cap needs no rate.** A tender larger than the sale's
  own total in that same currency is refused (`TenderExceedsSaleError`), which catches a
  zero too many. A mixed-currency sale is capped in neither column: a dollar handset and
  a som case on one invoice can be settled together in either currency, so any column
  would refuse real payments.
- **B7 is done, and it is what makes the som figures count.** The report now carries
  `rate_gain`: the money that really crossed the counter, less what the same deals
  convert to at the day's rate. A $600 sale settled with 7 620 000 som on a day quoted
  at 12 500 earned 120 000 som; a handset valued at $330 and bought for 3 600 000 som
  earned 525 000. Margin plus rate gain is `profit`, and it equals the subtraction an
  owner does on paper: money in less money out. A sale nobody recorded a settlement for
  is skipped rather than counted as a total loss, and a store-credit sale counts its
  som debt as settled, because that is som the store is owed.
- **B4 needed no formula in the end, and Q5 is answered.** Shops do not compute the debt
  from a rate and a percentage; a seller names a som figure across the counter. That is
  what makes the split mechanical: on a sale settled at the counter the gap between the
  money taken and the converted price is a *rate* the seller applied, and on a
  store-credit sale no rate was applied at all, so the whole gap is the markup. The
  report splits by payment type, not by arithmetic, and carries `instalment_income`
  beside `rate_gain`.
- **A payment against a debt is not money arriving twice.** `settled_sales` counts the
  debt on a store-credit sale and its payments on every other kind. Counting both read
  a 7 800 000 debt with an 800 000 down payment as 8 600 000 received, which is 800 000
  of invented earnings every instalment sale.
- **A debt counts as earned at confirm, not when it is collected.** A sale on twelve
  months lands whole in the month it was made. That is what accrual means and it is what
  `AccrualFigures` has always done; it is written here because the som profit line makes
  it visible for the first time.
- **The `runs_till` switch left the settings screen.** After B1 and B2 it gates neither
  the tender nor the trade-in payout, and the shift screens it is for do not exist yet.
  The column, the API field and the form value all stay; only the control is gone, so a
  save cannot silently turn it off. It comes back with B5.

### Decisions taken for B1

- Two rates, sale and buyback. They differ in a real shop and the difference is itself
  earnings.
- No rate for today: take the most recent one, warn, do not block the sale. A shop that
  cannot sell because a manager overslept is worse than a stale rate.
- A reminder on sign-in when the rate is stale, plus the entry card on the dashboard.
- The som figure is recorded for every `PAID_IN_FULL` sale, not behind `runs_till`. The
  flag stays and comes into its own in B5, where it gates shift screens.
- Owner and manager may set the rate. Everyone may see it.

---

## 5. Rate policy, for when reporting starts converting (B7)

To be printed on the report itself, not only written here.

- **Transactions** (revenue, cost of goods, payments) convert at the rate recorded on the
  transaction's own date.
- **Balances** (stock on hand, customer debt, cash) convert at the closing rate of the
  period.
- The difference between those two passes is **currency gain and loss**, and it gets its
  own line. It will not be zero, and that is the correct result, not a defect.
- A closed month never moves. Re-running March's report in December must return the same
  figures it returned in April. This is what makes the snapshot on the document, rather
  than a lookup at read time, the right mechanism.

---

## 6. Open questions for the owners

Order matters. The first four decide the schema.

1. Which currency do you count profit in? If I say "you made X this month", do you want X
   in dollars or in som?
2. When a customer pays som for a dollar-priced phone, what goes in your notebook, the
   dollars or the som? (This, not question 1, reveals the real answer.)
3. Where does your selling rate come from? Who sets it, how often, one rate for the whole
   shop, and may a seller depart from it?
4. Is your buying rate for used handsets the same as your selling rate? How far apart?
5. Instalments: how is the debt figure calculated? Price at the rate plus a percentage?
   What percentage, over what term? Do you consider that markup profit, or part of the
   price?
6. May a debtor pay in dollars? (Today the system refuses: `PaymentPoster` requires som.)
7. Do you keep a till? Is there an opening balance each day? Do rent, wages and supplier
   payments go through the same notebook?
8. How many places does money sit: som drawer, dollar drawer, terminal, Payme, Click, the
   owner's safe? Do you move money between them?
9. Do you take stock from a supplier on credit? Do you need to see what you owe them?
10. Do you hold dollars as savings? If the rate rises and you sold nothing, is that profit
    for the month?
11. Who may see cost and margin?
12. Do your figures reconcile at month end today, on your own notebook? By how much do
    they differ, and what do you do about it?

**Question 12 is the most useful one.** It reveals the accuracy they actually need. A shop
living happily with a 3% gap does not need double-entry built for it.

**Answered so far.** Q1: profit is counted in som. Q5: there is no instalment formula, a
seller names a som figure, which is what B4 was blocked on.

**Blocking:** B5 needs 7 and 8.
