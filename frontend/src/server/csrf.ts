import "server-only";

import { NextResponse, type NextRequest } from "next/server";

import { CSRF_HEADER } from "@/lib/csrf";

/**
 * Cookie auth means the browser attaches the session to any request aimed at
 * this host, whoever started it. `SameSite=Lax` stops the plain cross-site
 * case, but it compares registrable domains, so a sibling subdomain still
 * counts as "same site". Origin is compared exactly and closes that.
 */

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function forbidden(): NextResponse {
  return NextResponse.json(
    { detail: "Cross-site request rejected" },
    { status: 403 },
  );
}

/** `null` when the request is ours; a ready 403 otherwise. */
export function rejectCrossSite(request: NextRequest): NextResponse | null {
  if (SAFE_METHODS.has(request.method)) return null;

  if (request.headers.get(CSRF_HEADER) !== "1") return forbidden();

  const site = request.headers.get("sec-fetch-site");
  if (site) return site === "same-origin" ? null : forbidden();

  return sameHost(request) ? null : forbidden();
}

/**
 * For a route reached by navigation rather than fetch: it can carry neither a
 * custom header nor an Origin, so Sec-Fetch-Site is the only signal. `none` is
 * a typed URL or a bookmark, which is legitimate here.
 */
export function rejectCrossSiteNavigation(
  request: NextRequest,
): NextResponse | null {
  const site = request.headers.get("sec-fetch-site");
  return site === "cross-site" || site === "same-site" ? forbidden() : null;
}

function sameHost(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return false;

  try {
    return new URL(origin).host === publicHost(request);
  } catch {
    return false;
  }
}

/** Behind Caddy the public name arrives as a forwarded header, not as the socket's. */
function publicHost(request: NextRequest): string {
  return (
    request.headers.get("x-forwarded-host") ??
    request.headers.get("host") ??
    request.nextUrl.host
  );
}

/**
 * `request.nextUrl.origin` is unreliable on the standalone server: when a
 * request arrives without a usable `Host` header (a keep-alive connection
 * reused after the client sat idle is the usual trigger), Next falls back to
 * the server's own bind address, which is `0.0.0.0:3000` here (see
 * `frontend/Dockerfile`'s `HOSTNAME=0.0.0.0`). Forwarded/Host headers, same
 * as `publicHost`, are the trustworthy source.
 */
export function publicOrigin(request: NextRequest): string {
  return `${request.nextUrl.protocol}//${publicHost(request)}`;
}
