import "server-only";

import { cookies } from "next/headers";
import type { NextResponse } from "next/server";

export const ACCESS_COOKIE = "apex_at";
export const REFRESH_COOKIE = "apex_rt";

export type Tokens = { accessToken: string; refreshToken: string };

/**
 * Both cookies outlive the access JWT on purpose. The JWT's own 15-minute
 * expiry is the real gate; the cookie only has to survive long enough for the
 * proxy to notice a 401 and exchange the refresh token. Expiring the access
 * cookie early would log people out while a perfectly good refresh token sat
 * in the jar.
 */
const COOKIE_OPTIONS = {
  httpOnly: true,
  sameSite: "lax",
  path: "/",
  secure: process.env.NODE_ENV === "production",
  maxAge: 60 * 60 * 24 * 30,
} as const;

export async function readTokens(): Promise<{
  accessToken?: string;
  refreshToken?: string;
}> {
  const jar = await cookies();
  return {
    accessToken: jar.get(ACCESS_COOKIE)?.value,
    refreshToken: jar.get(REFRESH_COOKIE)?.value,
  };
}

export function setTokensOn(res: NextResponse, tokens: Tokens): void {
  res.cookies.set(ACCESS_COOKIE, tokens.accessToken, COOKIE_OPTIONS);
  res.cookies.set(REFRESH_COOKIE, tokens.refreshToken, COOKIE_OPTIONS);
}

export function clearTokensOn(res: NextResponse): void {
  res.cookies.set(ACCESS_COOKIE, "", { ...COOKIE_OPTIONS, maxAge: 0 });
  res.cookies.set(REFRESH_COOKIE, "", { ...COOKIE_OPTIONS, maxAge: 0 });
}
