import { getTranslations } from "next-intl/server";

import { AcceptInviteForm } from "@/app/accept-invite/AcceptInviteForm";
import { AuthShell } from "@/components/auth/AuthShell";
import { ErrorAlert } from "@/components/ErrorAlert";

export default async function AcceptInvitePage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;
  const t = await getTranslations("auth");

  return (
    <AuthShell
      title={t("acceptInviteTitle")}
      subtitle={token ? t("acceptInviteSubtitle") : undefined}
    >
      {token ? <AcceptInviteForm token={token} /> : <ErrorAlert message={t("missingToken")} />}
    </AuthShell>
  );
}
