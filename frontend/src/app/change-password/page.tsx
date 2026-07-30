import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { ChangePasswordForm } from "@/app/change-password/ChangePasswordForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { loadMe } from "@/server/me";

/**
 * Deliberately outside the (app) group: that layout redirects here whenever
 * `mustChangePassword` is set, so living inside it would loop.
 */
export default async function ChangePasswordPage() {
  const result = await loadMe();
  if (result.status === "anonymous") redirect("/login");
  if (result.status === "expired")
    redirect("/api/auth/reauth?next=/change-password");

  const t = await getTranslations("auth");

  return (
    <AuthShell
      title={t("changePasswordTitle")}
      subtitle={t("changePasswordSubtitle")}
    >
      <ChangePasswordForm forced={result.me.mustChangePassword} />
    </AuthShell>
  );
}
