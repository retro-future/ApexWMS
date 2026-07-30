import { NextResponse, type NextRequest } from "next/server";

import { callBackend } from "@/server/backend";

/**
 * Anonymous, so it cannot go through /api/backend/* (which requires a session
 * cookie). No tokens are issued here — the invitee signs in normally after.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.text();

  const upstream = await callBackend("/auth/accept-invite", {
    method: "POST",
    body: payload,
  });

  const text = await upstream.text();
  return new NextResponse(text || null, {
    status: upstream.status,
    headers: text ? { "Content-Type": "application/json" } : undefined,
  });
}
