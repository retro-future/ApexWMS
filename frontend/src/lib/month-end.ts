/**
 * What the month-end screen needs that is not JSX.
 *
 * The row lists live here rather than inline in the component because each
 * table is a grid of figures against currencies, and a row and a column that
 * drift apart produce a plausible-looking wrong number.
 *
 * The report is two questions. **Stock value** rolls opening inventory to
 * closing: every line is a move on the shelf, so `stockMoveMinor` shows the
 * *inventory* direction — a supplier return reads as goods leaving (`-`),
 * not as the credit coming back (`+`). **Sales** keeps §4.6's cash signs,
 * because there revenue in and cost out is exactly the point.
 *
 * `formatPeriod` is the reason this module exists at all. `useDateFormat`
 * renders in the browser's timezone, which would show a Tashkent January as
 * beginning at 11:00 PM on 31 December and make FR-10.8 look like a bug. The
 * period belongs to the store, so it is formatted in the store's zone.
 */

import type {
  AccrualFigures,
  Currency,
  CurrencySubtotal,
  DocumentStatus,
  MarginPercent,
  PaymentType,
  Period,
  TransactionType,
} from "@/lib/types";

/** The stock-value block, opening first and closing last. */
export const STOCK_BRIDGE_ROWS = [
  "openingInventory",
  "purchases",
  "costOfGoods",
  "writeOffs",
  "supplierReturnCredits",
  "countAdjustments",
  "closingInventory",
] as const satisfies readonly (keyof AccrualFigures)[];

/** The moves between opening and closing — the rows `stockMoveMinor` signs. */
export const STOCK_MOVE_ROWS = [
  "purchases",
  "costOfGoods",
  "writeOffs",
  "supplierReturnCredits",
  "countAdjustments",
] as const satisfies readonly (keyof AccrualFigures)[];

export type StockMoveRow = (typeof STOCK_MOVE_ROWS)[number];

/** The sales block: revenue, the cost against it, and their sum. */
export const SALES_ROWS = [
  "revenue",
  "costOfGoods",
  "margin",
] as const satisfies readonly (keyof AccrualFigures)[];

/** Every money row, for working out which currency columns to show. */
const MONEY_ROWS = [
  ...STOCK_BRIDGE_ROWS,
  "revenue",
  "margin",
] as const satisfies readonly (keyof AccrualFigures)[];

/**
 * How each move affects stock value, versus its stored §4.6 cash sign. A
 * `PURCHASE` is stored negative (money left) but adds to the shelf; a
 * `SUPPLIER_RETURN_CREDIT` is stored positive (money came back) but takes
 * goods off it. This is the frontend twin of `INVENTORY_SIGN` in the
 * backend's `cost_pools.py` — the two have to agree or the bridge stops
 * landing on `closingInventory`.
 */
const INVENTORY_SIGN: Record<StockMoveRow, 1 | -1> = {
  purchases: -1,
  costOfGoods: 1,
  writeOffs: 1,
  supplierReturnCredits: -1,
  countAdjustments: 1,
};

/** One move's effect on stock value in one currency, sign and all. */
export function stockMoveMinor(
  figures: AccrualFigures,
  row: StockMoveRow,
  currency: Currency,
): number {
  return amountIn(figures[row], currency) * INVENTORY_SIGN[row];
}

/** The ledger category each stock-bridge move is folded from. */
export const STOCK_MOVE_LEDGER_TYPE: Record<StockMoveRow, TransactionType> = {
  purchases: "purchase",
  costOfGoods: "cogs",
  writeOffs: "write_off_loss",
  supplierReturnCredits: "supplier_return_credit",
  countAdjustments: "count_adjustment",
};

/** The period's calendar dates in the **store's** month, `YYYY-MM-DD`. */
function monthDates(period: Period): { from: string; to: string } {
  const month = String(period.month).padStart(2, "0");
  // Day 0 of the next month is the last day of this one.
  const lastDay = new Date(period.year, period.month, 0).getDate();
  return {
    from: `${period.year}-${month}-01`,
    to: `${period.year}-${month}-${String(lastDay).padStart(2, "0")}`,
  };
}

/**
 * A month-end figure drilled into: the financial ledger, one category, the
 * report's month. Opening/closing inventory and margin have no such link —
 * they are folds and derivations, not a list.
 */
export function ledgerHref(txnType: TransactionType, period: Period): string {
  const { from, to } = monthDates(period);
  return `/reports/financial-ledger?txnType=${txnType}&from=${from}&to=${to}`;
}

/**
 * The debt figures link to the invoices that carry them: store-credit sales
 * confirmed in the month. This is the one the debtor list cannot answer —
 * it drops a sale the moment its balance reaches zero.
 */
export function invoicesHref({
  paymentType,
  status,
  period,
}: {
  paymentType: PaymentType;
  status: DocumentStatus;
  period: Period;
}): string {
  const { from, to } = monthDates(period);
  return (
    `/invoices?paymentType=${paymentType}&status=${status}` +
    `&confirmedFrom=${from}&confirmedTo=${to}`
  );
}

/** Stable, so the columns do not reorder when a period touches only som. */
const CURRENCY_ORDER: Currency[] = ["USD", "UZS"];

export function lastCompletedMonth(now: Date): { year: number; month: number } {
  const month = now.getMonth(); // 0-11, so this is already the month before
  return month === 0
    ? { year: now.getFullYear() - 1, month: 12 }
    : { year: now.getFullYear(), month };
}

/** `{2026, 1}` → `"2026-01"`, the value a `<input type="month">` holds. */
export function toMonthInput({
  year,
  month,
}: {
  year: number;
  month: number;
}): string {
  return `${year}-${String(month).padStart(2, "0")}`;
}

/** The inverse, or null when the input is empty or half-typed. */
export function fromMonthInput(
  value: string,
): { year: number; month: number } | null {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (month < 1 || month > 12) return null;
  return { year, month };
}

/**
 * The currencies the period actually touched, so the table gets a column per
 * currency and no more. A store that has only ever dealt in dollars should not
 * grow an empty som column.
 */
export function currenciesIn(figures: AccrualFigures): Currency[] {
  const touched = new Set<Currency>();
  for (const row of MONEY_ROWS) {
    for (const subtotal of figures[row] as CurrencySubtotal[]) {
      touched.add(subtotal.currency);
    }
  }
  return CURRENCY_ORDER.filter((currency) => touched.has(currency));
}

/**
 * One figure's amount in one currency, or zero in it — never a figure borrowed
 * from the other column.
 */
export function amountIn(
  subtotals: CurrencySubtotal[],
  currency: Currency,
): number {
  return (
    subtotals.find((subtotal) => subtotal.currency === currency)?.amountMinor ??
    0
  );
}

/** Null where revenue was zero, which is a month with no margin to state. */
export function percentIn(
  percentages: MarginPercent[],
  currency: Currency,
): string | null {
  return (
    percentages.find((entry) => entry.currency === currency)?.percent ?? null
  );
}

/** e.g. "2025-12-31 00:00 – 2026-01-31 00:00 (Asia/Tashkent)". */
export function formatPeriod(period: Period): string {
  const format = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: period.timezone,
  });
  const start = format.format(new Date(period.start)).replace(",", "");
  const end = format.format(new Date(period.end)).replace(",", "");
  return `${start} – ${end} (${period.timezone})`;
}
