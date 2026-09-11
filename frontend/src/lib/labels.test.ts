import { describe, expect, it } from "vitest";

import en from "@/../messages/en.json";
import ru from "@/../messages/ru.json";
import uz from "@/../messages/uz.json";
import { RATE_KINDS, TRACE_EVENT_KINDS, TRANSACTION_TYPES } from "@/lib/types";

/**
 * Every value the server can send has a label, in every locale.
 *
 * A missing one is invisible to `tsc` and to every other test: next-intl
 * throws at render time on the one screen that happens to show that value,
 * which in practice means a customer finds it. Three separate misses in one
 * week (a trace kind, then both tender categories) is what this exists for.
 *
 * It deliberately checks only that nothing is missing, never that nothing is
 * spare. A block may legitimately hold a key no enum sends —
 * `deviceStatus.customer_returned` labels a separate badge — and treating
 * one of those as dead is how a working label gets deleted.
 */
const LOCALES = { en, ru, uz };

describe.each([
  ["reports.txnType", TRANSACTION_TYPES, (m: typeof en) => m.reports.txnType],
  ["reports.traceKind", TRACE_EVENT_KINDS, (m: typeof en) => m.reports.traceKind],
  ["rates.kind", RATE_KINDS, (m: typeof en) => m.rates.kind],
] as const)("%s", (_name, values, pick) => {
  it.each(Object.keys(LOCALES))("has a label for every value in %s", (locale) => {
    const labels = pick(LOCALES[locale as keyof typeof LOCALES] as typeof en);
    const missing = values.filter((value) => !(value in labels));

    expect(missing).toEqual([]);
  });
});
