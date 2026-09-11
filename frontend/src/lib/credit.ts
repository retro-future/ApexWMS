/**
 * The refusals a credit sale can see coming, worked out on the client.
 *
 * Same job as `confirmBlockers` in ./invoices.ts and the same disclaimer:
 * this is **not** an enforcement point. The server checks every one of these
 * again and refuses on its own terms. It exists so the seller finds out
 * while the customer is still standing at the counter, rather than after
 * they have walked away with the phone in their hand.
 *
 * Every figure here is som. UZS has exponent 0 (PRD §4.5), so a som amount
 * *is* its own minor amount and there is no conversion in this file — the
 * seller quotes a som total for a dollar-priced phone in their head, and
 * that figure is the debt.
 *
 * Pure functions, deliberately free of React, so they are testable without
 * a DOM.
 */

import { inputToMoney, isValidPriceInput } from "@/lib/money";
import type { Currency, Payment, PaymentType, SalesInvoice } from "@/lib/types";

/** What the confirm dialog has collected so far. */
export type CreditTerms = {
  paymentType: PaymentType;
  creditCompanyId: string | null;
  contractRef: string;
  /** Major-unit som strings, exactly as they are sent. */
  debt: string;
  downPayment: string;
  /** Paid in full only: what the customer handed over, and in what. */
  tendered: string;
  tenderedCurrency: Currency;
};

export const EMPTY_TERMS: CreditTerms = {
  paymentType: "paid_in_full",
  creditCompanyId: null,
  contractRef: "",
  debt: "",
  downPayment: "",
  tendered: "",
  tenderedCurrency: "UZS",
};

/** A som input as a number, or null when it is blank or malformed. */
export function somMinor(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed || !isValidPriceInput(trimmed, "UZS")) return null;
  return Number(trimmed);
}

export type TermsBlocker =
  | "customerRequired"
  | "debtRequired"
  | "companyRequired"
  | "downPaymentTooLarge"
  | "tenderMalformed"
  | "tenderTooLarge";

/**
 * Why this sale cannot be confirmed on these terms yet.
 *
 * `customerRequired` is the one worth stating out loud: an invoice may be
 * raised for a walk-in (FR-4.1), but a debt may not — it would be money the
 * store knows it is owed and cannot say by whom (§4.7).
 */
export function termsBlockers(
  invoice: SalesInvoice,
  terms: CreditTerms,
): TermsBlocker[] {
  if (terms.paymentType === "credit_company") {
    return terms.creditCompanyId ? [] : ["companyRequired"];
  }
  if (terms.paymentType === "paid_in_full") {
    const tendered = terms.tendered.trim();
    if (!tendered) return [];
    if (!isValidPriceInput(tendered, terms.tenderedCurrency)) return ["tenderMalformed"];
    return overTheSale(invoice, tendered, terms.tenderedCurrency)
      ? ["tenderTooLarge"]
      : [];
  }
  if (terms.paymentType !== "store_credit") return [];

  const blockers: TermsBlocker[] = [];
  if (!invoice.customerId) blockers.push("customerRequired");

  const debt = somMinor(terms.debt);
  if (debt === null || debt <= 0) {
    blockers.push("debtRequired");
    return blockers;
  }
  if ((somMinor(terms.downPayment) ?? 0) > debt) {
    blockers.push("downPaymentTooLarge");
  }
  return blockers;
}

/**
 * More money than the sale asks for, when the two can be compared at all.
 *
 * Only a sale priced in this one currency can be: a dollar handset and a som
 * case on one invoice can be settled together in either currency, and no
 * column would mean anything without a rate. Mirrors the server's own rule.
 */
export function overTheSale(
  invoice: SalesInvoice,
  tendered: string,
  currency: Currency,
): boolean {
  const charged = invoice.subtotals;
  if (charged.length !== 1 || charged[0].currency !== currency) return false;
  const amount = inputToMoney(tendered, currency);
  return amount !== null && amount.minor > charged[0].minor;
}

/** What `POST /invoices/{id}/confirm` is sent. Omits what does not apply. */
export function confirmBody(terms: CreditTerms): Record<string, unknown> {
  if (terms.paymentType === "credit_company") {
    return {
      paymentType: terms.paymentType,
      creditCompanyId: terms.creditCompanyId,
      ...(terms.contractRef.trim() ? { contractRef: terms.contractRef.trim() } : {}),
    };
  }
  if (terms.paymentType === "store_credit") {
    const down = terms.downPayment.trim();
    return {
      paymentType: terms.paymentType,
      debt: terms.debt.trim(),
      ...(down ? { downPayment: down } : {}),
    };
  }
  const tendered = terms.tendered.trim();
  return {
    paymentType: terms.paymentType,
    // Omitted when blank: a store that runs no till confirms exactly as it
    // did before, and the server records nothing.
    ...(tendered
      ? { tendered, tenderedCurrency: terms.tenderedCurrency }
      : {}),
  };
}

/** Whether this sale still has a balance somebody has to settle. */
export function isOpenDebt(invoice: SalesInvoice): boolean {
  return invoice.paymentType === "store_credit" && (invoice.remaining?.minor ?? 0) > 0;
}

/**
 * What the store is holding and now owes back (FR-11.11).
 *
 * A cancelled sale's debt is void, but the money the customer handed over is
 * not — it stays in the ledger and has to be refunded by hand.
 */
export function refundDueMinor(invoice: SalesInvoice): number {
  if (invoice.status !== "cancelled") return 0;
  return Math.max(invoice.paid?.minor ?? 0, 0);
}

/** Payments oldest first, with reversals beside the rows they undo. */
export function reversedPaymentIds(payments: Payment[]): Set<string> {
  return new Set(
    payments
      .map((payment) => payment.reversesPaymentId)
      .filter((id): id is string => id !== null),
  );
}

/**
 * The currencies whose rows have not been reversed away.
 *
 * A counter sale takes one tender per currency: half in dollars and half in
 * som is two true facts, a second som row is a doubled figure. The server
 * keeps the same rule, so this only decides what the screen offers.
 */
export function standingCurrencies(payments: Payment[]): Set<Currency> {
  const undone = reversedPaymentIds(payments);
  return new Set(
    payments
      .filter((payment) => !payment.isReversal && !undone.has(payment.id))
      .map((payment) => payment.amount.currency),
  );
}
