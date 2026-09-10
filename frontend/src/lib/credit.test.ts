import { describe, expect, it } from "vitest";

import {
  confirmBody,
  EMPTY_TERMS,
  isOpenDebt,
  refundDueMinor,
  reversedPaymentIds,
  somMinor,
  termsBlockers,
  type CreditTerms,
} from "@/lib/credit";
import type { DocumentStatus, Payment, SalesInvoice } from "@/lib/types";

function invoice(overrides: Partial<SalesInvoice> = {}): SalesInvoice {
  return {
    id: "invoice-1",
    number: "INV-2026-0001",
    status: "draft" as DocumentStatus,
    locationId: "location-1",
    customerId: null,
    note: null,
    createdBy: "user-1",
    createdAt: "2026-08-19T09:00:00Z",
    confirmedBy: null,
    confirmedAt: null,
    cancelledBy: null,
    cancelledAt: null,
    cancellationReason: null,
    lines: [],
    subtotals: [],
    paymentType: "paid_in_full",
    creditCompanyId: null,
    contractRef: null,
    debt: null,
    paid: { minor: 0, currency: "UZS" },
    relieved: { minor: 0, currency: "UZS" },
    remaining: { minor: 0, currency: "UZS" },
    tendered: [],
    payments: [],
    belowCostAlerts: [],
    ...overrides,
  };
}

function terms(overrides: Partial<CreditTerms> = {}): CreditTerms {
  return { ...EMPTY_TERMS, ...overrides };
}

function payment(id: string, overrides: Partial<Payment> = {}): Payment {
  return {
    id,
    salesInvoiceId: "invoice-1",
    occurredAt: "2026-08-19T09:30:00Z",
    amount: { minor: 800000, currency: "USD" },
    method: "cash",
    userId: "user-1",
    note: null,
    reversesPaymentId: null,
    isReversal: false,
    ...overrides,
  };
}

describe("somMinor", () => {
  it("reads a som figure as its own minor amount", () => {
    // UZS has exponent 0, so there is nothing to multiply by.
    expect(somMinor("7800000")).toBe(7800000);
  });

  it("is null on a blank input rather than zero", () => {
    expect(somMinor("   ")).toBeNull();
  });

  it("refuses a fractional som", () => {
    expect(somMinor("800000.50")).toBeNull();
  });
});

describe("termsBlockers", () => {
  it("lets a walk-in pay in full", () => {
    expect(termsBlockers(invoice(), terms())).toEqual([]);
  });

  it("asks for the company financing the sale", () => {
    expect(termsBlockers(invoice(), terms({ paymentType: "credit_company" }))).toEqual([
      "companyRequired",
    ]);
  });

  it("clears once a company is picked, with no customer needed", () => {
    // FR-11.4: the company pays, so there is no debtor to name.
    const chosen = terms({ paymentType: "credit_company", creditCompanyId: "uzum" });
    expect(termsBlockers(invoice(), chosen)).toEqual([]);
  });

  it("refuses an anonymous debt (§4.7)", () => {
    const credit = terms({ paymentType: "store_credit", debt: "7800000" });
    expect(termsBlockers(invoice(), credit)).toEqual(["customerRequired"]);
  });

  it("names both refusals at once", () => {
    expect(termsBlockers(invoice(), terms({ paymentType: "store_credit" }))).toEqual([
      "customerRequired",
      "debtRequired",
    ]);
  });

  it("treats a zero debt as no debt", () => {
    const named = invoice({ customerId: "customer-1" });
    expect(termsBlockers(named, terms({ paymentType: "store_credit", debt: "0" }))).toEqual(
      ["debtRequired"],
    );
  });

  it("refuses a down payment above the debt", () => {
    const named = invoice({ customerId: "customer-1" });
    const credit = terms({
      paymentType: "store_credit",
      debt: "7800000",
      downPayment: "8000000",
    });
    expect(termsBlockers(named, credit)).toEqual(["downPaymentTooLarge"]);
  });

  it("allows a customer paying the whole debt up front", () => {
    const named = invoice({ customerId: "customer-1" });
    const credit = terms({
      paymentType: "store_credit",
      debt: "7800000",
      downPayment: "7800000",
    });
    expect(termsBlockers(named, credit)).toEqual([]);
  });

  it("passes the milestone's terms", () => {
    const named = invoice({ customerId: "customer-1" });
    const credit = terms({
      paymentType: "store_credit",
      debt: "7800000",
      downPayment: "800000",
    });
    expect(termsBlockers(named, credit)).toEqual([]);
  });
});

describe("confirmBody", () => {
  it("sends the payment type alone for a cash sale", () => {
    expect(confirmBody(terms())).toEqual({ paymentType: "paid_in_full" });
  });

  it("sends what was tendered, with the currency it was taken in", () => {
    const cash = terms({ tendered: "7620000", tenderedCurrency: "UZS" });

    expect(confirmBody(cash)).toEqual({
      paymentType: "paid_in_full",
      tendered: "7620000",
      tenderedCurrency: "UZS",
    });
  });

  it("omits a blank tender, so a store with no till confirms as before", () => {
    expect(confirmBody(terms({ tendered: "  " }))).toEqual({
      paymentType: "paid_in_full",
    });
  });

  it("omits a blank contract reference rather than sending null", () => {
    const financed = terms({
      paymentType: "credit_company",
      creditCompanyId: "uzum",
      contractRef: "  ",
    });
    expect(confirmBody(financed)).toEqual({
      paymentType: "credit_company",
      creditCompanyId: "uzum",
    });
  });

  it("trims the contract reference it does send", () => {
    const financed = terms({
      paymentType: "credit_company",
      creditCompanyId: "uzum",
      contractRef: " UZ-4417 ",
    });
    expect(confirmBody(financed)).toMatchObject({ contractRef: "UZ-4417" });
  });

  it("omits the down payment when the customer pays nothing today", () => {
    const credit = terms({ paymentType: "store_credit", debt: "7800000" });
    expect(confirmBody(credit)).toEqual({
      paymentType: "store_credit",
      debt: "7800000",
    });
  });

  it("sends both figures for the milestone's sale", () => {
    const credit = terms({
      paymentType: "store_credit",
      debt: " 7800000 ",
      downPayment: " 800000 ",
    });
    expect(confirmBody(credit)).toEqual({
      paymentType: "store_credit",
      debt: "7800000",
      downPayment: "800000",
    });
  });

  it("never leaks a company onto a store-credit sale", () => {
    const credit = terms({
      paymentType: "store_credit",
      debt: "7800000",
      creditCompanyId: "uzum",
    });
    expect(confirmBody(credit)).not.toHaveProperty("creditCompanyId");
  });
});

describe("isOpenDebt", () => {
  it("is true while som is still owed", () => {
    const open = invoice({
      status: "confirmed",
      paymentType: "store_credit",
      remaining: { minor: 7000000, currency: "UZS" },
    });
    expect(isOpenDebt(open)).toBe(true);
  });

  it("is false once the balance reaches zero", () => {
    const settled = invoice({ status: "confirmed", paymentType: "store_credit" });
    expect(isOpenDebt(settled)).toBe(false);
  });

  it("is false for a financed sale, whatever it is worth", () => {
    const financed = invoice({ status: "confirmed", paymentType: "credit_company" });
    expect(isOpenDebt(financed)).toBe(false);
  });
});

describe("refundDueMinor", () => {
  it("is nothing while the sale stands", () => {
    const live = invoice({
      status: "confirmed",
      paymentType: "store_credit",
      paid: { minor: 800000, currency: "UZS" },
    });
    expect(refundDueMinor(live)).toBe(0);
  });

  it("is everything the customer paid once the sale is cancelled (FR-11.11)", () => {
    // The debt is void; the money the customer handed over is not.
    const cancelled = invoice({
      status: "cancelled",
      paymentType: "store_credit",
      paid: { minor: 1600000, currency: "UZS" },
      relieved: { minor: 0, currency: "UZS" },
      remaining: { minor: 0, currency: "UZS" },
    });
    expect(refundDueMinor(cancelled)).toBe(1600000);
  });

  it("is nothing on a cancelled sale nobody paid against", () => {
    expect(refundDueMinor(invoice({ status: "cancelled" }))).toBe(0);
  });
});

describe("reversedPaymentIds", () => {
  it("is empty when nothing was undone", () => {
    expect(reversedPaymentIds([payment("a"), payment("b")]).size).toBe(0);
  });

  it("names the row a reversal undoes, not the reversal itself", () => {
    const undo = payment("b", {
      amount: { minor: -800000, currency: "USD" },
      reversesPaymentId: "a",
      isReversal: true,
    });
    const reversed = reversedPaymentIds([payment("a"), undo]);

    expect(reversed.has("a")).toBe(true);
    expect(reversed.has("b")).toBe(false);
  });
});
