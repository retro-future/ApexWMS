import { redirect } from "next/navigation";

import { AppShellFrame } from "@/components/shell/AppShellFrame";
import { PlatformOperatorNotice } from "@/components/shell/PlatformOperatorNotice";
import { loadMe } from "@/server/me";

/**
 * The auth guard for everything inside the app.
 *
 * Next 16 deprecated `middleware` in favour of `proxy` and recommends
 * avoiding both, so the check lives here in a Server Component — which also
 * means the page never renders before identity is known.
 */
export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const result = await loadMe();

  if (result.status === "anonymous") redirect("/login");

  // A Server Component cannot write cookies, so it cannot store a rotated
  // token; bounce through a Route Handler that can.
  if (result.status === "expired") redirect("/api/auth/reauth?next=/");

  const me = result.me;

  // Advisory on the server (PRD §3.5 defers the hard gate), enforced here.
  if (me.mustChangePassword) redirect("/change-password");

  // Covers platform operators, whose token carries no tenant claim at all.
  if (!me.tenantId) return <PlatformOperatorNotice me={me} />;

  return <AppShellFrame me={me}>{children}</AppShellFrame>;
}
