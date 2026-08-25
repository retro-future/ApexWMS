"use client";

import { Button } from "@mantine/core";
import { IconFileText } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

/**
 * Opens a document's PDF in a new tab (FR-8.1).
 *
 * A plain anchor rather than a fetch: the proxy is same-origin and the session
 * is an httpOnly cookie, so a top-level navigation carries it with no token
 * plumbing, and the browser gets its own PDF viewer for free.
 *
 * The caller decides whether to render one at all. A draft has nothing to
 * print and the server refuses it, and the order's page is a list of costs
 * while the return note carries no money — so the guards differ per document
 * and none of them belong here.
 */
export function OpenPdfButton({ href }: { href: string }) {
  const t = useTranslations("documents");

  return (
    <Button
      component="a"
      href={href}
      target="_blank"
      rel="noreferrer"
      variant="light"
      leftSection={<IconFileText size={16} />}
    >
      {t("openPdf")}
    </Button>
  );
}
