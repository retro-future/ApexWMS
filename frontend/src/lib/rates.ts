import type { Money } from "@/lib/types";

/**
 * What a dollar figure works out to in som at a given rate, in minor units.
 *
 * A display aid only. The figure is never sent anywhere and never prefilled
 * into the tender field: what the seller actually took is a fact, and a
 * number the screen guessed for them is not.
 *
 * Null when there is no rate, or nothing priced in dollars to convert.
 */
export function somAtRate(subtotals: Money[], somPerUsd: string | null): number | null {
  if (!somPerUsd) return null;
  const rate = Number(somPerUsd);
  if (!Number.isFinite(rate) || rate <= 0) return null;

  const usd = subtotals.find((amount) => amount.currency === "USD");
  if (!usd || usd.minor === 0) return null;

  // USD has two decimal places and som has none, so the cents divide out.
  return Math.round((usd.minor * rate) / 100);
}

/**
 * The rate a sale was actually struck at, som taken over dollars charged.
 *
 * Null unless exactly one som tender meets one dollar total: a sale settled
 * half in dollars implies no single rate, and inventing one would be the
 * cross-currency arithmetic the money model exists to prevent.
 */
export function impliedRate(subtotals: Money[], tendered: Money[]): number | null {
  const usd = subtotals.find((amount) => amount.currency === "USD");
  const som = tendered.find((amount) => amount.currency === "UZS");
  if (!usd || !som || usd.minor === 0) return null;
  if (tendered.length !== 1 || subtotals.length !== 1) return null;
  return (som.minor * 100) / usd.minor;
}
