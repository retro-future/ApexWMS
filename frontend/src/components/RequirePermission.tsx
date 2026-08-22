"use client";

import { useTranslations } from "next-intl";

import { ErrorAlert } from "@/components/ErrorAlert";
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
    return <ErrorAlert message={t("forbidden")} />;
  }

  return <>{children}</>;
}
