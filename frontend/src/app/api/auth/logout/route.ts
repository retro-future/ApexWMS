import { NextResponse, type NextRequest } from "next/server";

import { rejectCrossSite } from "@/server/csrf";
import { clearTokensOn } from "@/server/session";

/**
 * There is no backend logout endpoint — refresh tokens are revoked by
 * rotation and by password change, not by an explicit call. Dropping the
 * cookies is the whole operation.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const blocked = rejectCrossSite(request);
  if (blocked) return blocked;

  const res = new NextResponse(null, { status: 204 });
  clearTokensOn(res);
  return res;
}
