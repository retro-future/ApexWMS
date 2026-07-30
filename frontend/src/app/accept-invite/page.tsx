import { Alert } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { getTranslations } from "next-intl/server";

import { AcceptInviteForm } from "@/app/accept-invite/AcceptInviteForm";
import { AuthShell } from "@/components/auth/AuthShell";

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
      {token ? (
        <AcceptInviteForm token={token} />
      ) : (
        <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
          {t("missingToken")}
        </Alert>
      )}
    </AuthShell>
  );
}
