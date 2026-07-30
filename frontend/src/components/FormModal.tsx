"use client";

import { Alert, Button, Group, Modal, Stack } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

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
          {error && (
            <Alert
              variant="light"
              color="red"
              icon={<IconAlertCircle size={18} />}
            >
              {error}
            </Alert>
          )}

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
