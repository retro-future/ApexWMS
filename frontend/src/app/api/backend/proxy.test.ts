import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GET } from "@/app/api/backend/[...path]/route";

const { callBackend, readTokens } = vi.hoisted(() => ({
  callBackend: vi.fn(),
  readTokens: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("@/server/backend", () => ({ callBackend }));
vi.mock("@/server/refresh", () => ({ refreshTokens: vi.fn() }));
vi.mock("@/server/session", () => ({
  readTokens,
  setTokensOn: vi.fn(),
  clearTokensOn: vi.fn(),
}));

function request(path: string) {
  return new NextRequest(`http://localhost:3000/api/backend/${path}`);
}

function context(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

beforeEach(() => {
  vi.clearAllMocks();
  readTokens.mockResolvedValue({ accessToken: "at", refreshToken: "rt" });
});

describe("the BFF proxy", () => {
  it("passes a PDF through byte for byte", async () => {
    // Reading the upstream body as text and re-encoding it corrupts every
    // byte outside ASCII, which is most of a PDF.
    const pdf = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x37, 0x0a, 0x80, 0xff, 0xfe]);
    callBackend.mockResolvedValue(
      new Response(pdf, {
        status: 200,
        headers: {
          "content-type": "application/pdf",
          "content-disposition": 'inline; filename="INV-2026-0001.pdf"',
        },
      }),
    );

    const res = await GET(
      request("invoices/invoice-1/pdf"),
      context(["invoices", "invoice-1", "pdf"]),
    );

    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("application/pdf");
    // The filename the browser puts on the tab and on a save.
    expect(res.headers.get("Content-Disposition")).toBe(
      'inline; filename="INV-2026-0001.pdf"',
    );
    expect(new Uint8Array(await res.arrayBuffer())).toEqual(pdf);
  });

  it("still hands JSON back unchanged", async () => {
    callBackend.mockResolvedValue(
      new Response(JSON.stringify({ success: true, data: { id: "invoice-1" } }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const res = await GET(request("invoices/invoice-1"), context(["invoices", "invoice-1"]));

    expect(res.headers.get("Content-Type")).toBe("application/json");
    expect(await res.json()).toEqual({ success: true, data: { id: "invoice-1" } });
  });

  it("forwards a bodyless status without inventing one", async () => {
    callBackend.mockResolvedValue(new Response(null, { status: 204 }));

    const res = await GET(request("invoices/x/lines/y"), context(["invoices", "x", "lines", "y"]));

    expect(res.status).toBe(204);
    expect(res.headers.get("Content-Type")).toBeNull();
  });

  it("refuses without a session rather than calling the backend", async () => {
    readTokens.mockResolvedValue({ accessToken: undefined, refreshToken: undefined });

    const res = await GET(request("invoices"), context(["invoices"]));

    expect(res.status).toBe(401);
    expect(callBackend).not.toHaveBeenCalled();
  });
});
