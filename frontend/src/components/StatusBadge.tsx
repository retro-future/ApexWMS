"use client";

import { Badge } from "@mantine/core";
import { useTranslations } from "next-intl";

/** Nothing is ever deleted (FR-2.4) — records are deactivated instead. */
export function StatusBadge({ isActive }: { isActive: boolean }) {
  const t = useTranslations("common");
  return (
    <Badge size="sm" variant="light" color={isActive ? "teal" : "gray"}>
      {isActive ? t("active") : t("inactive")}
    </Badge>
  );
}
