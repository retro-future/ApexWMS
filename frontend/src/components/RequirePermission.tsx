"use client";

import { Alert } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { useCan } from "@/components/MeProvider";

/** The nav hides the button that leads here, but a pasted URL should say why, not 403 later. */
export function RequirePermission({
  permission,
  children,
}: {
  permission: string;
  children: React.ReactNode;
}) {
  const t = useTranslations("errors");
  const can = useCan();

  if (!can(permission)) {
    return (
      <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
        {t("forbidden")}
      </Alert>
    );
  }

  return <>{children}</>;
}
