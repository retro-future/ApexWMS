"use client";

import { Center, Loader } from "@mantine/core";

import { ErrorAlert } from "@/components/ErrorAlert";

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
  return <ErrorAlert message={message} />;
}
