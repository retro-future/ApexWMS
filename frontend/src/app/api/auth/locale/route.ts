import { NextResponse, type NextRequest } from "next/server";

import { LOCALE_COOKIE, isLocale } from "@/i18n/config";
import { rejectCrossSite } from "@/server/csrf";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const blocked = rejectCrossSite(request);
  if (blocked) return blocked;

  const { locale } = (await request.json()) as { locale?: string };

  if (!isLocale(locale)) {
    return NextResponse.json({ detail: "Unknown locale" }, { status: 400 });
  }

  const res = new NextResponse(null, { status: 204 });
  res.cookies.set(LOCALE_COOKIE, locale, {
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  });
  return res;
}
