import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DeviceStatusBadge } from "@/components/DeviceStatusBadge";
import { DEVICE_STATUSES } from "@/lib/types";
import { renderWithProviders } from "@/test/render";

describe("DeviceStatusBadge", () => {
  it.each(DEVICE_STATUSES)("labels %s", (status) => {
    renderWithProviders(<DeviceStatusBadge status={status} />);

    // next-intl renders the raw key when it has no message, so a missing
    // label shows up as the key itself rather than as a thrown error here.
    expect(screen.queryByText(new RegExp(status))).not.toBeInTheDocument();
  });

  it("labels the returned badge, which is not a status", () => {
    // Regression: `deviceStatus.customer_returned` was deleted as a dead key
    // because no `DeviceStatus` has that value. It labels this second badge.
    renderWithProviders(<DeviceStatusBadge status="in_stock" returned />);

    expect(screen.queryByText(/customer_returned/)).not.toBeInTheDocument();
    expect(screen.getByText("Returned by customer")).toBeInTheDocument();
  });
});
