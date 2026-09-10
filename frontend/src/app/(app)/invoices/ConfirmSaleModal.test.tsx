import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmSaleModal } from "@/app/(app)/invoices/ConfirmSaleModal";
import { Permission } from "@/lib/permissions";
import type { SalesInvoice } from "@/lib/types";
import { makeMe, renderWithProviders } from "@/test/render";

const { apiGetPaged } = vi.hoisted(() => ({ apiGetPaged: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGetPaged,
}));

const DRAFT: SalesInvoice = {
  id: "invoice-1",
  number: "INV-2026-0001",
  status: "draft",
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
};

const SELLER = makeMe(
  [Permission.Sales.Manage, Permission.CreditSale.Create, Permission.CreditCompany.View],
  "tenant.seller",
);

function open(invoice: SalesInvoice = DRAFT, onSubmit = vi.fn()) {
  renderWithProviders(
    <ConfirmSaleModal
      invoice={invoice}
      quote={[{ currency: "USD", minor: 60000 }]}
      busy={false}
      error={null}
      onClose={vi.fn()}
      onSubmit={onSubmit}
    />,
    { me: SELLER },
  );
  return onSubmit;
}

async function pickStoreCredit(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("radio", { name: "Store credit" }));
}

beforeEach(() => {
  vi.clearAllMocks();
  apiGetPaged.mockResolvedValue({
    items: [{ id: "uzum", name: "Uzum Nasiya", contactName: null, phone: null, email: null, isActive: true }],
    page: 1,
    pageSize: 200,
    totalItems: 1,
    pagesCount: 1,
  });
});

describe("ConfirmSaleModal", () => {
  it("opens on cash, with the quote the seller is converting from", () => {
    open();

    expect(screen.getByRole("radio", { name: "Paid in full" })).toBeChecked();
    expect(screen.getByText("$600.00")).toBeInTheDocument();
    expect(screen.queryByLabelText("Debt")).not.toBeInTheDocument();
  });

  it("confirms a cash sale with the payment type alone", async () => {
    const user = userEvent.setup();
    const onSubmit = open();

    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(onSubmit).toHaveBeenCalledWith({ paymentType: "paid_in_full" });
  });

  it("refuses an anonymous debt and says why (§4.7)", async () => {
    const user = userEvent.setup();
    const onSubmit = open();

    await pickStoreCredit(user);

    expect(
      screen.getByText("A debt needs a customer. Pick one before selling on store credit."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("still asks for the som figure once a customer is named", async () => {
    const user = userEvent.setup();
    const onSubmit = open({ ...DRAFT, customerId: "customer-1" });

    await pickStoreCredit(user);

    expect(
      screen.getByText("Enter the som debt the customer agreed to."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows what is left after the down payment and sends both (FR-11.5)", async () => {
    const user = userEvent.setup();
    const onSubmit = open({ ...DRAFT, customerId: "customer-1" });

    await pickStoreCredit(user);
    await user.type(screen.getByLabelText("Debt"), "7800000");
    await user.type(screen.getByLabelText("Down payment"), "800000");

    expect(
      screen.getByText("Remaining after the down payment: 7 000 000 so'm"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(onSubmit).toHaveBeenCalledWith({
      paymentType: "store_credit",
      debt: "7800000",
      downPayment: "800000",
    });
  });

  it("refuses a down payment above the debt", async () => {
    const user = userEvent.setup();
    const onSubmit = open({ ...DRAFT, customerId: "customer-1" });

    await pickStoreCredit(user);
    await user.type(screen.getByLabelText("Debt"), "7800000");
    await user.type(screen.getByLabelText("Down payment"), "8000000");

    expect(
      screen.getByText("The down payment is larger than the debt."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("names the company on a financed sale, and asks for no customer", async () => {
    const user = userEvent.setup();
    const onSubmit = open();

    await user.click(screen.getByRole("radio", { name: "Credit company" }));
    await waitFor(() => expect(apiGetPaged).toHaveBeenCalled());

    await user.click(screen.getByRole("combobox", { name: "Company" }));
    await user.click(await screen.findByRole("option", { name: "Uzum Nasiya" }));

    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(onSubmit).toHaveBeenCalledWith({
      paymentType: "credit_company",
      creditCompanyId: "uzum",
    });
  });

  it("leaves credit closed to a seller who may not lend", async () => {
    renderWithProviders(
      <ConfirmSaleModal
        invoice={DRAFT}
        quote={[]}
        busy={false}
        error={null}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
      { me: makeMe([Permission.Sales.Manage], "tenant.seller") },
    );

    expect(screen.getByRole("radio", { name: "Store credit" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Credit company" })).toBeDisabled();
  });
});
