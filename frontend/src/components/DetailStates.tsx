"use client";

import { Alert, Center, Loader } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";

/** The loading spinner every detail/settings page shows while its query resolves. */
export function DetailLoading() {
  return (
    <Center p="xl">
      <Loader size="sm" />
    </Center>
  );
}

/** The error alert every detail/settings page shows when its query fails or the resource is missing. */
export function DetailError({ message }: { message: string }) {
  return (
    <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
      {message}
    </Alert>
  );
}
