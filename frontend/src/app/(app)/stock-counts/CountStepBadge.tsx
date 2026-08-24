"use client";

import { Badge } from "@mantine/core";
import { useTranslations } from "next-intl";

import { countStep, type CountStep } from "@/lib/stock-counts";
import type { StockCount } from "@/lib/types";

/**
 * A count has four steps and `DocumentStatus` has three values, so
 * `DocumentStatusBadge` cannot tell the whole story: a closed count is still
 * a `draft`, one that has found its discrepancies and applied none. This
 * badge reads the step instead, so "Counting" and "Closed" stop looking
 * identical on the list.
 */
const COLOR: Record<CountStep, string> = {
  counting: "blue",
  closed: "yellow",
  confirmed: "teal",
  cancelled: "red",
};

export function CountStepBadge({ count }: { count: StockCount }) {
  const t = useTranslations("stockCounts.step");
  const step = countStep(count);

  return (
    <Badge size="sm" variant="light" color={COLOR[step]}>
      {t(step)}
    </Badge>
  );
}
