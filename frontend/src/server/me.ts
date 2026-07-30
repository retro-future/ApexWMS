import "server-only";

import type { Me } from "@/lib/types";
import { backendData, callBackend } from "@/server/backend";
import { readTokens } from "@/server/session";

export type MeResult =
  | { status: "ok"; me: Me }
  | { status: "anonymous" }
  | { status: "expired" };

/**
 * Identity for a server-rendered page. `expired` means "the access JWT is
 * stale but a refresh token may still be good" — the caller should bounce
 * through /api/auth/reauth rather than straight to the login screen.
 */
export async function loadMe(): Promise<MeResult> {
  const { accessToken, refreshToken } = await readTokens();
  if (!accessToken) return { status: "anonymous" };

  const res = await callBackend("/auth/me", { accessToken });

  if (res.status === 401) {
    return refreshToken ? { status: "expired" } : { status: "anonymous" };
  }

  if (!res.ok) {
    // Not an auth problem — let the error boundary say so instead of
    // silently bouncing the user around the login screen.
    throw new Error(`Could not load the current user (HTTP ${res.status})`);
  }

  const me = await backendData<Me>(res);
  if (!me) throw new Error("The backend returned an unreadable /auth/me body");

  return { status: "ok", me };
}
