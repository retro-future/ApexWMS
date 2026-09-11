import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RatesCard } from "@/app/(app)/RatesCard";
import { Permission } from "@/lib/permissions";
import type { CurrentRates } from "@/lib/types";
import { makeMe, renderWithProviders } from "@/test/render";

const { apiGet, apiSend } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiSend: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGet,
  apiSend,
}));

const MANAGER = makeMe(
  [Permission.ExchangeRate.View, Permission.ExchangeRate.Manage],
  "tenant.manager",
);
const SELLER = makeMe([Permission.ExchangeRate.View], "tenant.seller");

function quoted(somPerUsd: string, isStale: boolean): CurrentRates {
  return {
    sale: {
      id: "rate-1",
      kind: "sale",
      somPerUsd,
      effectiveOn: isStale ? "2026-08-18" : "2026-08-19",
      setAt: "2026-08-18T06:00:00Z",
      userId: "user-1",
      isStale,
    },
    buyback: null,
    today: "2026-08-19",
  };
}

const EMPTY: CurrentRates = { sale: null, buyback: null, today: "2026-08-19" };

function render(rates: CurrentRates, me = MANAGER) {
  apiGet.mockResolvedValue(rates);
  apiSend.mockResolvedValue(rates.sale);
  renderWithProviders(<RatesCard />, { me });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("the rate of the day", () => {
  it("shows the rate in force", async () => {
    render(quoted("12000", false));

    expect(await screen.findByDisplayValue("12000")).toBeInTheDocument();
    expect(screen.queryByText(/update it for today/i)).not.toBeInTheDocument();
  });

  it("warns when the rate on file is yesterday's", async () => {
    render(quoted("12000", true));

    expect(await screen.findByText(/last quoted on 2026-08-18/i)).toBeInTheDocument();
  });

  it("says so when no rate has ever been quoted", async () => {
    render(EMPTY);

    expect(await screen.findByText(/no rate has been quoted yet/i)).toBeInTheDocument();
  });

  it("lets a seller read the rate but not change it", async () => {
    render(quoted("12000", false), SELLER);

    expect(await screen.findByDisplayValue("12000")).toBeDisabled();
    expect(screen.queryByRole("button", { name: /save rate/i })).not.toBeInTheDocument();
  });

  it("lets an unchanged rate be quoted again for today", async () => {
    // A rate that has not moved for days still has to be quoted, or those
    // days are read at an older figure.
    render(quoted("12000", true));

    const button = await screen.findByRole("button", {
      name: /confirm today's rate/i,
    });
    expect(button).toBeEnabled();
  });

  it("has nothing to save while today's rate is already on file", async () => {
    render(quoted("12000", false));

    expect(await screen.findByRole("button", { name: /save rate/i })).toBeDisabled();
  });

  it("writes the same number again when today's rate is confirmed", async () => {
    render(quoted("12000", true));

    await userEvent.click(
      await screen.findByRole("button", { name: /confirm today's rate/i }),
    );

    await waitFor(() => expect(apiSend).toHaveBeenCalled());
    expect(apiSend).toHaveBeenCalledWith("POST", "/exchange-rates", {
      kind: "sale",
      somPerUsd: "12000",
    });
  });

  it("is hidden from anyone who may not see rates", async () => {
    render(quoted("12000", false), makeMe([], "tenant.seller"));

    expect(screen.queryByText(/rate of the day/i)).not.toBeInTheDocument();
  });
});
