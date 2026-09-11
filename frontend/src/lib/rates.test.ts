import { describe, expect, it } from "vitest";

import { impliedRate, somAtRate } from "@/lib/rates";
import type { Money } from "@/lib/types";

const usd = (minor: number): Money => ({ minor, currency: "USD" });
const uzs = (minor: number): Money => ({ minor, currency: "UZS" });

describe("somAtRate", () => {
  it("turns a dollar total into som at the quoted rate", () => {
    expect(somAtRate([usd(60000)], "12000")).toBe(7_200_000);
  });

  it("rounds a fractional rate to whole som", () => {
    expect(somAtRate([usd(60000)], "12345.5")).toBe(7_407_300);
  });

  it("is null with no rate quoted", () => {
    expect(somAtRate([usd(60000)], null)).toBeNull();
  });

  it("is null for a sale with nothing priced in dollars", () => {
    expect(somAtRate([uzs(7_200_000)], "12000")).toBeNull();
  });

  it("refuses a rate that is not a positive number", () => {
    expect(somAtRate([usd(60000)], "0")).toBeNull();
    expect(somAtRate([usd(60000)], "twelve")).toBeNull();
  });
});

describe("impliedRate", () => {
  it("is the som taken over the dollars charged", () => {
    expect(impliedRate([usd(60000)], [uzs(7_200_000)])).toBe(12_000);
  });

  it("shows the seller's own rate when it differs from the quote", () => {
    // 4 025 000 som for a $350 phone is 11 500, not the 12 000 quoted.
    expect(impliedRate([usd(35000)], [uzs(4_025_000)])).toBe(11_500);
  });

  it("is null when nothing has been tendered yet", () => {
    expect(impliedRate([usd(60000)], [])).toBeNull();
  });

  it("is null for a sale settled in two currencies", () => {
    // Half in dollars implies no single rate, and inventing one would be
    // the cross-currency arithmetic §4.5 exists to prevent.
    expect(impliedRate([usd(60000)], [usd(30000), uzs(3_600_000)])).toBeNull();
  });

  it("is null for a sale priced in two currencies", () => {
    expect(impliedRate([usd(60000), uzs(50_000)], [uzs(7_250_000)])).toBeNull();
  });
});
