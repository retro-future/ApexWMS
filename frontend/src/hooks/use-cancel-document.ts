"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { useDocumentAction } from "@/hooks/use-document";
import { errorMessage, notifySuccess } from "@/lib/notify";

/**
 * The cancel lifecycle shared by every document detail page: a reason
 * modal, a POST to /cancel, and the "cancelled" notice on success.
 * `setError` stays page-owned rather than living in this hook's own state,
 * because confirm and cancel report into the same alert slot on every page
 * that has both actions.
 */
export function useCancelDocument(
  resource: string,
  id: string,
  setError: (message: string | null) => void,
) {
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const [opened, setOpened] = useState(false);

  const cancel = useDocumentAction<unknown, { reason: string | null }>(resource, id, {
    path: "/cancel",
  });

  async function run(reason: string | null) {
    setError(null);
    try {
      await cancel.mutateAsync({ reason });
      notifySuccess(tDoc("cancelled"));
      setOpened(false);
    } catch (error) {
      setError(errorMessage(error, tCommon("retry")));
    }
  }

  return {
    opened,
    open: () => setOpened(true),
    close: () => setOpened(false),
    busy: cancel.isPending,
    run,
  };
}
