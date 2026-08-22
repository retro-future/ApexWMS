"use client";

import { Button, Group, Modal, Stack } from "@mantine/core";
import { useTranslations } from "next-intl";

import { ErrorAlert } from "@/components/ErrorAlert";

/** Chrome for the small create/edit dialogs the simpler resources use. */
export function FormModal({
  opened,
  onClose,
  title,
  onSubmit,
  busy,
  error,
  submitLabel,
  children,
}: {
  opened: boolean;
  onClose: () => void;
  title: string;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  busy?: boolean;
  error?: string | null;
  submitLabel: string;
  children: React.ReactNode;
}) {
  const t = useTranslations("common");

  return (
    <Modal opened={opened} onClose={onClose} title={title} centered>
      <form onSubmit={onSubmit} noValidate>
        <Stack gap="md">
          <ErrorAlert message={error} />

          {children}

          <Group justify="flex-end" mt="xs">
            <Button variant="default" onClick={onClose} disabled={busy}>
              {t("cancel")}
            </Button>
            <Button type="submit" loading={busy}>
              {submitLabel}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
