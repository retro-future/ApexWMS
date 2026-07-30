import { NextResponse, type NextRequest } from "next/server";

import { refreshTokens } from "@/server/refresh";
import { clearTokensOn, readTokens, setTokensOn } from "@/server/session";

/**
 * A bounce that exists because Server Components may not write cookies.
 *
 * Data fetching refreshes transparently inside the proxy, but a *full page
 * load* after the 15-minute access JWT has expired renders a Server Component
 * that can only notice the 401 — it cannot store the rotated token. So the
 * layout redirects here, this handler does the exchange (it is a Route
 * Handler, so it can set cookies), and sends the user back into the app.
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const origin = request.nextUrl.origin;
  const target = safeNext(request.nextUrl.searchParams.get("next"));

  const { refreshToken } = await readTokens();
  if (!refreshToken) return toLogin(origin);

  const rotated = await refreshTokens(refreshToken);
  if (!rotated) {
    const res = toLogin(origin);
    clearTokensOn(res);
    return res;
  }

  const res = NextResponse.redirect(new URL(target, origin));
  setTokensOn(res, rotated);
  return res;
}

/** Only same-origin paths — never let a query param become an open redirect. */
function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/";
  return value;
}

function toLogin(origin: string): NextResponse {
  return NextResponse.redirect(new URL("/login?expired=1", origin));
}
