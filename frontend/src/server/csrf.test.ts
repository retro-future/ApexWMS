import { NextRequest } from "next/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

const { rejectCrossSite, rejectCrossSiteNavigation } = await import(
  "@/server/csrf"
);

function post(headers: Record<string, string>) {
  return new NextRequest("http://apexwms.test/api/backend/write-offs", {
    method: "POST",
    headers: { host: "apexwms.test", ...headers },
  });
}

const OURS = { "x-apex-request": "1" };

describe("rejectCrossSite", () => {
  it("lets a read through untouched", () => {
    const get = new NextRequest("http://apexwms.test/api/backend/invoices");
    expect(rejectCrossSite(get)).toBeNull();
  });

  it("rejects a write with no header, which is all a cross-site form can send", () => {
    expect(rejectCrossSite(post({}))?.status).toBe(403);
  });

  it("accepts our own fetch", () => {
    expect(
      rejectCrossSite(post({ ...OURS, "sec-fetch-site": "same-origin" })),
    ).toBeNull();
  });

  it("rejects a sibling subdomain, which SameSite treats as same site", () => {
    expect(
      rejectCrossSite(post({ ...OURS, "sec-fetch-site": "same-site" }))?.status,
    ).toBe(403);
  });

  it("rejects an outright cross-site write", () => {
    expect(
      rejectCrossSite(post({ ...OURS, "sec-fetch-site": "cross-site" }))?.status,
    ).toBe(403);
  });

  it("falls back to Origin when the browser sends no Sec-Fetch-Site", () => {
    expect(
      rejectCrossSite(post({ ...OURS, origin: "http://apexwms.test" })),
    ).toBeNull();
    expect(
      rejectCrossSite(post({ ...OURS, origin: "http://evil.test" }))?.status,
    ).toBe(403);
  });

  it("rejects a write carrying neither Sec-Fetch-Site nor Origin", () => {
    expect(rejectCrossSite(post(OURS))?.status).toBe(403);
  });

  it("compares against the forwarded host, since Caddy terminates TLS", () => {
    expect(
      rejectCrossSite(
        post({
          ...OURS,
          origin: "https://apexwms.com",
          "x-forwarded-host": "apexwms.com",
        }),
      ),
    ).toBeNull();
  });
});

describe("rejectCrossSiteNavigation", () => {
  function navigate(headers: Record<string, string>) {
    return new NextRequest("http://apexwms.test/api/auth/reauth", { headers });
  }

  it("allows an in-app redirect and a typed URL", () => {
    expect(rejectCrossSiteNavigation(navigate({ "sec-fetch-site": "same-origin" }))).toBeNull();
    expect(rejectCrossSiteNavigation(navigate({ "sec-fetch-site": "none" }))).toBeNull();
  });

  it("rejects a link planted on another site", () => {
    expect(
      rejectCrossSiteNavigation(navigate({ "sec-fetch-site": "cross-site" }))?.status,
    ).toBe(403);
  });
});
