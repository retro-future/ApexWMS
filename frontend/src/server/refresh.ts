import "server-only";

import { callBackend } from "@/server/backend";
import type { Tokens } from "@/server/session";

/**
 * Refresh-token exchanges, keyed by the token being spent.
 *
 * This file exists because the backend *rotates* refresh tokens and treats a
 * replayed one as theft: presenting an already-spent token revokes every
 * token the user has. Two browser requests that 401 at the same moment (easy
 * — two lists loading on one page after the 15-minute access JWT expired)
 * both carry the same refresh cookie, so without coordination the second one
 * looks like a replay and signs the user out completely.
 *
 * Deduplicating only the *in-flight* window is not enough. If the first
 * exchange finishes before the second request even reaches this function, the
 * second still holds the old token and would replay it. So a settled result
 * is kept for a grace period and handed to any latecomer, which is correct:
 * they were asking about the same token and deserve the same answer.
 */
const RESULT_GRACE_MS = 30_000;

const exchanges = new Map<string, Promise<Tokens | null>>();

async function exchange(refreshToken: string): Promise<Tokens | null> {
  try {
    const res = await callBackend("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refreshToken }),
    });

    if (!res.ok) return null;

    const envelope = (await res.json()) as {
      data?: { accessToken?: string; refreshToken?: string } | null;
    };
    const data = envelope.data;
    if (!data?.accessToken || !data?.refreshToken) return null;

    return { accessToken: data.accessToken, refreshToken: data.refreshToken };
  } catch {
    // Never reject: every caller shares this promise, and a rejection here
    // would surface as an unhandled error rather than a clean re-login.
    return null;
  }
}

export function refreshTokens(refreshToken: string): Promise<Tokens | null> {
  const existing = exchanges.get(refreshToken);
  if (existing) return existing;

  const tracked = exchange(refreshToken);
  exchanges.set(refreshToken, tracked);

  void tracked.then(() => {
    const timer = setTimeout(
      () => exchanges.delete(refreshToken),
      RESULT_GRACE_MS,
    );
    // Don't hold the process open just to forget a token.
    timer.unref?.();
  });

  return tracked;
}
