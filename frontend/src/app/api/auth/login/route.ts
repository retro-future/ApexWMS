import { NextResponse, type NextRequest } from "next/server";

import type { LoginResult } from "@/lib/types";
import { callBackend } from "@/server/backend";
import { setTokensOn } from "@/server/session";

type LoginData = {
  accessToken: string;
  refreshToken: string;
  mustChangePassword?: boolean;
  tenantId?: string | null;
  role?: LoginResult["role"];
  appRoles?: LoginResult["appRoles"];
};

export async function POST(request: NextRequest): Promise<NextResponse> {
  const { email, password } = (await request.json()) as {
    email?: string;
    password?: string;
  };

  const upstream = await callBackend("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  const payload = (await upstream.json().catch(() => null)) as {
    data?: LoginData;
    detail?: unknown;
  } | null;

  if (!upstream.ok || !payload?.data) {
    return NextResponse.json(
      { detail: payload?.detail ?? "Sign in failed" },
      { status: upstream.status === 200 ? 502 : upstream.status },
    );
  }

  const data = payload.data;

  // The tokens stop here: the browser gets only what the UI needs to route.
  const result: LoginResult = {
    mustChangePassword: Boolean(data.mustChangePassword),
    tenantId: data.tenantId ?? null,
    role: data.role ?? null,
    appRoles: data.appRoles ?? [],
  };

  const res = NextResponse.json(result);
  setTokensOn(res, {
    accessToken: data.accessToken,
    refreshToken: data.refreshToken,
  });
  return res;
}
