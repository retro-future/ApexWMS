"use client";

import { Badge } from "@mantine/core";
import { useTranslations } from "next-intl";

import type { DocumentStatus } from "@/lib/types";

/**
 * Every document shares one lifecycle (PRD §4.4), so it shares one badge.
 * Distinct from `StatusBadge`, which is the catalog's active/inactive flag —
 * a cancelled document is not a deactivated row.
 */
const COLOR: Record<DocumentStatus, string> = {
  draft: "gray",
  confirmed: "teal",
  cancelled: "red",
};

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const t = useTranslations("documents");
  return (
    <Badge size="sm" variant="light" color={COLOR[status]}>
      {t(`status.${status}`)}
    </Badge>
  );
}
