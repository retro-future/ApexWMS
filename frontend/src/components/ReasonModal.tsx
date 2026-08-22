"use client";

import { Button, Group, Modal, Stack, Text, Textarea } from "@mantine/core";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";

/**
 * Confirming an irreversible act, with an optional note for the record.
 *
 * Cancelling a confirmed document writes compensating movements rather than
 * deleting anything (§4.3 rule 2), so the reason is not paperwork — it is
 * the only explanation the ledger will ever carry for why the reversal
 * exists.
 */
export function ReasonModal({
  opened,
  onClose,
  title,
  description,
  submitLabel,
  color,
  busy,
  error,
  onSubmit,
}: {
  opened: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  submitLabel: string;
  color?: string;
  busy?: boolean;
  error?: string | null;
  onSubmit: (reason: string | null) => void;
}) {
  const t = useTranslations("common");
  const tDoc = useTranslations("documents");
  const [reason, setReason] = useState("");

  return (
    <Modal opened={opened} onClose={onClose} title={title} centered>
      <Stack gap="md">
        <ErrorAlert message={error} />

        {description && (
          <Text size="sm" c="dimmed">
            {description}
          </Text>
        )}

        <Textarea
          label={tDoc("reason")}
          description={tDoc("reasonHint")}
          value={reason}
          onChange={(event) => setReason(event.currentTarget.value)}
          autosize
          minRows={2}
        />

        <Group justify="flex-end">
          <Button variant="default" onClick={onClose} disabled={busy}>
            {t("cancel")}
          </Button>
          <Button
            color={color}
            loading={busy}
            onClick={() => onSubmit(reason.trim() || null)}
          >
            {submitLabel}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
