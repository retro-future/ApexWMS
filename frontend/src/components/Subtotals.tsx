"use client";

import { Group, Text } from "@mantine/core";

import { formatMoney } from "@/lib/money";
import type { Currency } from "@/lib/types";

/**
 * One figure per currency, side by side.
 *
 * PRD §4.5 rule 4: totals are per-currency, never summed and never
 * converted. There is deliberately no `total` prop for a caller to add
 * $6.00 to 50 000 so'm into — the payload has no such field either.
 *
 * The prop is narrower than `CurrencySubtotal` on purpose: a draft invoice's
 * quote is assembled client-side from minor amounts and has no major-unit
 * string to offer, and nothing here reads one.
 */
export function Subtotals({
  subtotals,
  size = "sm",
  fw,
}: {
  subtotals: { currency: Currency; amountMinor: number }[];
  size?: string;
  fw?: number;
}) {
  if (subtotals.length === 0) return <Text size={size} c="dimmed">—</Text>;

  return (
    <Group gap="sm" wrap="wrap">
      {subtotals.map((subtotal) => (
        <Text key={subtotal.currency} size={size} fw={fw}>
          {formatMoney(subtotal.amountMinor, subtotal.currency)}
        </Text>
      ))}
    </Group>
  );
}
