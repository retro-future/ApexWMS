import { NextResponse, type NextRequest } from "next/server";

import { callBackend } from "@/server/backend";
import { refreshTokens } from "@/server/refresh";
import {
  clearTokensOn,
  readTokens,
  setTokensOn,
  type Tokens,
} from "@/server/session";

/**
 * The BFF. Every browser call to the API lands here, gets the bearer token
 * attached from the httpOnly cookie, and is forwarded to FastAPI.
 *
 * The browser therefore never holds a token, never learns the backend's
 * address, and never makes a cross-origin request.
 */

type Context = { params: Promise<{ path: string[] }> };

const BODYLESS_STATUSES = new Set([204, 205, 304]);

function unauthorized(): NextResponse {
  return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
}

async function handle(
  request: NextRequest,
  context: Context,
): Promise<NextResponse> {
  const { path } = await context.params;
  const target = `/${path.join("/")}${request.nextUrl.search}`;
  const method = request.method;

  // Read once: the body may have to be replayed after a token refresh, and a
  // request stream can only be consumed a single time.
  const body =
    method === "GET" || method === "HEAD" ? undefined : await request.text();
  const contentType = request.headers.get("content-type");

  const { accessToken, refreshToken } = await readTokens();
  if (!accessToken) return unauthorized();

  let upstream = await callBackend(target, {
    method,
    body: body || undefined,
    accessToken,
    contentType,
  });

  let rotated: Tokens | null = null;

  if (upstream.status === 401 && refreshToken) {
    rotated = await refreshTokens(refreshToken);
    if (!rotated) {
      const res = unauthorized();
      clearTokensOn(res);
      return res;
    }
    upstream = await callBackend(target, {
      method,
      body: body || undefined,
      accessToken: rotated.accessToken,
      contentType,
    });
  }

  const hasBody = !BODYLESS_STATUSES.has(upstream.status);
  // Bytes, not text: a PDF decoded as UTF-8 and re-encoded is a corrupt
  // PDF, and `GET /invoices/{id}/pdf` is served straight through here.
  const payload = hasBody ? await upstream.arrayBuffer() : null;

  const headers = new Headers();
  if (hasBody) {
    headers.set(
      "Content-Type",
      upstream.headers.get("content-type") ?? "application/json",
    );
    // Carries the filename a browser puts on the tab and on a save.
    const disposition = upstream.headers.get("content-disposition");
    if (disposition) headers.set("Content-Disposition", disposition);
  }

  const res = new NextResponse(payload, { status: upstream.status, headers });

  if (rotated) setTokensOn(res, rotated);
  return res;
}

export const GET = handle;
export const POST = handle;
export const PATCH = handle;
export const PUT = handle;
export const DELETE = handle;
