/**
 * Money formatting.
 *
 * The two currencies do NOT share a decimal exponent (PRD §4.5):
 *
 *     USD → exponent 2   100000 minor units is $1,000.00
 *     UZS → exponent 0     1000 minor units is 1 000 so'm
 *
 * ISO 4217 nominally gives UZS exponent 2, but tiyin are defunct and the
 * backend deliberately treats so'm as exponent 0. Assuming a shared exponent
 * is the "classic 100× corruption bug" the PRD flags as a High risk, so
 * nothing here is allowed to guess: every function takes the currency.
 *
 * Formatting is done on strings rather than by dividing, because floats are
 * exactly what this system refuses to represent money with.
 */

import type { Currency, Money } from "@/lib/types";

const EXPONENT: Record<Currency, number> = { USD: 2, UZS: 0 };

/** Narrow no-break space — keeps "1 000" from wrapping mid-number. */
const UZS_GROUP_SEPARATOR = " ";

export function exponentOf(currency: Currency): number {
  return EXPONENT[currency];
}

function group(digits: string, separator: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, separator);
}

/** Split an integer minor amount into grouped major and fractional parts. */
function split(minor: number, currency: Currency, separator: string) {
  const exponent = exponentOf(currency);
  const negative = minor < 0;
  const digits = String(Math.abs(minor)).padStart(exponent + 1, "0");
  const cut = digits.length - exponent;
  return {
    sign: negative ? "-" : "",
    major: group(digits.slice(0, cut), separator),
    fraction: exponent ? digits.slice(cut) : "",
  };
}

/** `$599.00` for USD 59900; `12 000 so'm` for UZS 12000. */
export function formatMoney({ minor, currency }: Money): string {
  if (currency === "USD") {
    const { sign, major, fraction } = split(minor, currency, ",");
    return `${sign}$${major}.${fraction}`;
  }
  const { sign, major } = split(minor, currency, UZS_GROUP_SEPARATOR);
  return `${sign}${major}${UZS_GROUP_SEPARATOR}so'm`;
}

/** The same, but a nullish amount renders as a dash rather than crashing. */
export function formatMoneyOrDash(money: Money | null | undefined): string {
  return money ? formatMoney(money) : "—";
}

/**
 * What a price input may contain. UZS has no minor unit, so a decimal point
 * in a so'm price is a mistake rather than a rounding question.
 */
function priceInputPattern(currency: Currency): RegExp {
  return currency === "USD" ? /^\d+(\.\d{1,2})?$/ : /^\d+$/;
}

export function isValidPriceInput(value: string, currency: Currency): boolean {
  return priceInputPattern(currency).test(value.trim());
}

/**
 * Turn a minor amount back into something the price input can show, so
 * editing a product round-trips without ever touching a float.
 */
export function minorToInput(
  minor: number | null | undefined,
  currency: Currency,
): string {
  if (minor === null || minor === undefined) return "";
  const { sign, major, fraction } = split(minor, currency, "");
  return fraction ? `${sign}${major}.${fraction}` : `${sign}${major}`;
}

/** `minorToInput` for a whole `Money`; empty string when there is none. */
export function moneyToInput(money: Money | null | undefined): string {
  return money ? minorToInput(money.minor, money.currency) : "";
}
