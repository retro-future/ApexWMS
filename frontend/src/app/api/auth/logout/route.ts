import { NextResponse } from "next/server";

import { clearTokensOn } from "@/server/session";

/**
 * There is no backend logout endpoint — refresh tokens are revoked by
 * rotation and by password change, not by an explicit call. Dropping the
 * cookies is the whole operation.
 */
export async function POST(): Promise<NextResponse> {
  const res = new NextResponse(null, { status: 204 });
  clearTokensOn(res);
  return res;
}
