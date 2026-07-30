import { getTranslations } from "next-intl/server";

import { LoginForm } from "@/app/login/LoginForm";
import { AuthShell } from "@/components/auth/AuthShell";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ expired?: string; changed?: string }>;
}) {
  const params = await searchParams;
  const t = await getTranslations("auth");

  const notice = params.changed
    ? t("signedOutAfterPasswordChange")
    : params.expired
      ? t("sessionExpired")
      : undefined;

  return (
    <AuthShell title={t("signInTitle")} subtitle={t("signInSubtitle")}>
      <LoginForm notice={notice} />
    </AuthShell>
  );
}
