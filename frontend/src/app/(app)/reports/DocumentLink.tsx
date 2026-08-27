"use client";

import { Anchor, Text } from "@mantine/core";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { documentHref } from "@/app/(app)/reports/document-href";
import type { DocumentType } from "@/lib/types";

/** The document a ledger row came from, linked where the app has a page for it. */
export function DocumentLink({
  documentType,
  documentId,
  documentNumber,
}: {
  documentType: DocumentType;
  documentId: string;
  documentNumber: string | null;
}) {
  const t = useTranslations("reports");
  const href = documentHref(documentType, documentId);
  const label = documentNumber ?? t(`documentType.${documentType}`);

  if (!href) return <Text size="sm">{label}</Text>;

  return (
    <Anchor component={Link} href={href} size="sm">
      {label}
    </Anchor>
  );
}
