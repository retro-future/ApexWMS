import { describe, expect, it } from "vitest";

import {
  exponentOf,
  formatMoney,
  isValidPriceInput,
  minorToInput,
} from "@/lib/money";

/**
 * The exponent trap (PRD §4.5): USD has two decimal places and UZS has
 * none. Assuming a shared exponent corrupts every amount by a factor of
 * 100, and this module is the only place on the frontend where that can
 * happen — so it is the one place worth pinning down.
 */
/** So'm amounts are grouped with a narrow no-break space, not a plain one. */
const NBSP = " ";
const som = (grouped: string) => grouped.replaceAll(" ", NBSP);

describe("formatMoney", () => {
  it("reads a USD minor amount as cents", () => {
    expect(formatMoney({ minor: 100000, currency: "USD" })).toBe("$1,000.00");
    expect(formatMoney({ minor: 59900, currency: "USD" })).toBe("$599.00");
    expect(formatMoney({ minor: 5, currency: "USD" })).toBe("$0.05");
  });

  it("reads a UZS minor amount as whole so'm", () => {
    // The same integer, twelve thousand times apart in value.
    expect(formatMoney({ minor: 1000, currency: "UZS" })).toBe(som("1 000 so'm"));
    expect(formatMoney({ minor: 1000, currency: "USD" })).toBe("$10.00");
  });

  it("groups the large amounts a so'm price actually reaches", () => {
    expect(formatMoney({ minor: 12000000, currency: "UZS" })).toBe(som("12 000 000 so'm"));
  });

  it("keeps a negative amount signed", () => {
    expect(formatMoney({ minor: -33000, currency: "USD" })).toBe("-$330.00");
    expect(formatMoney({ minor: -4200000, currency: "UZS" })).toBe(som("-4 200 000 so'm"));
  });

  it("knows the two exponents apart", () => {
    expect(exponentOf("USD")).toBe(2);
    expect(exponentOf("UZS")).toBe(0);
  });
});

describe("minorToInput", () => {
  it("round-trips an amount back into its price field", () => {
    expect(minorToInput(59900, "USD")).toBe("599.00");
    expect(minorToInput(12000000, "UZS")).toBe("12000000");
  });

  it("leaves an unpriced field empty rather than showing zero", () => {
    expect(minorToInput(null, "USD")).toBe("");
    expect(minorToInput(undefined, "UZS")).toBe("");
  });
});

describe("isValidPriceInput", () => {
  it("accepts cents in dollars", () => {
    expect(isValidPriceInput("599", "USD")).toBe(true);
    expect(isValidPriceInput("599.9", "USD")).toBe(true);
    expect(isValidPriceInput("599.00", "USD")).toBe(true);
  });

  it("refuses a decimal point in so'm — tiyin are defunct", () => {
    expect(isValidPriceInput("50000", "UZS")).toBe(true);
    expect(isValidPriceInput("50000.50", "UZS")).toBe(false);
  });

  it("refuses anything that is not a plain number", () => {
    expect(isValidPriceInput("$599", "USD")).toBe(false);
    expect(isValidPriceInput("599.999", "USD")).toBe(false);
    expect(isValidPriceInput("", "USD")).toBe(false);
  });
});
