import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SettingsPage from "@/app/(app)/settings/page";
import { MAX_LOGO_BYTES } from "@/lib/letterhead";
import { Permission } from "@/lib/permissions";
import type { TenantSettings } from "@/lib/types";
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

const settings: TenantSettings = {
  timezone: "Asia/Tashkent",
  businessName: "Apex Mobile",
  address: "12 Amir Temur, Tashkent",
  hasLogo: false,
};

function png(size = 64): File {
  return new File([new Uint8Array(size)], "logo.png", { type: "image/png" });
}

/**
 * Mantine's FileInput shows a button and keeps the real input hidden behind
 * it, so the upload has to be aimed at the input itself.
 */
function fileInput(container: HTMLElement): HTMLInputElement {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("no file input on the page");
  return input;
}

beforeEach(() => {
  vi.clearAllMocks();
  apiGet.mockResolvedValue(settings);
  apiSend.mockResolvedValue(settings);
});

function render(permissions: string[], data: TenantSettings = settings) {
  apiGet.mockResolvedValue(data);
  return renderWithProviders(<SettingsPage />, { me: makeMe(permissions) });
}

const OWNER = [Permission.TenantSettings.View, Permission.TenantSettings.Manage];
const MEMBER = [Permission.TenantSettings.View];

describe("the letterhead", () => {
  it("saves every field, because a PUT replaces the whole document", async () => {
    // Sending the timezone alone blanks the business name and the address:
    // the server writes both unconditionally from a body that defaults them
    // to null. This is the assertion that keeps that from coming back.
    const user = userEvent.setup();
    render(OWNER);

    await user.type(await screen.findByLabelText("Business name"), "!");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith("PUT", "/settings/tenant", {
        timezone: "Asia/Tashkent",
        businessName: "Apex Mobile!",
        address: "12 Amir Temur, Tashkent",
      }),
    );
  });

  it("sends null rather than an empty string for a cleared field", async () => {
    const user = userEvent.setup();
    render(OWNER);

    await user.clear(await screen.findByLabelText("Address"));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith(
        "PUT",
        "/settings/tenant",
        expect.objectContaining({ address: null }),
      ),
    );
  });

  it("is read-only for anyone but the owner", async () => {
    render(MEMBER);

    expect(await screen.findByText("Only the store owner can change these.")).toBeInTheDocument();
    expect(screen.getByLabelText("Business name")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });
});

describe("the logo", () => {
  it("uploads a PNG as base64 without its data-URL prefix", async () => {
    const user = userEvent.setup();
    const { container } = render(OWNER);
    await screen.findByText("Logo");

    await user.upload(fileInput(container), png());

    await waitFor(() => expect(apiSend).toHaveBeenCalledTimes(1));
    const [method, path, payload] = apiSend.mock.calls[0]!;
    expect(method).toBe("PUT");
    expect(path).toBe("/settings/tenant/logo");
    expect((payload as { content: string }).content).not.toContain("base64,");
  });

  it("refuses a file the server would refuse, without asking it", async () => {
    const user = userEvent.setup();
    const { container } = render(OWNER);
    await screen.findByText("Logo");

    await user.upload(
      fileInput(container),
      new File([new Uint8Array(MAX_LOGO_BYTES + 1)], "big.png", { type: "image/png" }),
    );

    expect(
      await screen.findByText("That image is over 512 KB. Choose a smaller one."),
    ).toBeInTheDocument();
    expect(apiSend).not.toHaveBeenCalled();
  });

  it("clears it with an empty body, which is how the API says 'no logo'", async () => {
    const user = userEvent.setup();
    render(OWNER, { ...settings, hasLogo: true });

    await user.click(await screen.findByRole("button", { name: "Remove" }));

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith("PUT", "/settings/tenant/logo", {}),
    );
  });

  it("offers no way to change it to a member who may only read settings", async () => {
    const { container } = render(MEMBER, { ...settings, hasLogo: true });

    // They still see the logo that is set — it is on every document anyway.
    expect(await screen.findByRole("img", { name: "Logo" })).toBeInTheDocument();
    expect(container.querySelector('input[type="file"]')).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
  });
});
