"use client";

import { Alert } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";

/** The red inline alert for a page/form-level error. Renders nothing when `message` is falsy. */
export function ErrorAlert({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
      {message}
    </Alert>
  );
}
