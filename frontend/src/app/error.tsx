"use client";

import { Alert, Button, Card, Center, Group, Stack, Title } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect } from "react";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations("errors");
  const tCommon = useTranslations("common");
  const tNav = useTranslations("nav");

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <Center mih="100dvh" p="md">
      <Card withBorder shadow="sm" padding="xl" radius="md" maw={480}>
        <Stack gap="lg">
          <Title order={3}>{t("generic")}</Title>
          <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
            {error.message || t("generic")}
          </Alert>
          <Group justify="flex-end">
            <Button component={Link} href="/" variant="default">
              {tNav("dashboard")}
            </Button>
            <Button onClick={reset}>{tCommon("retry")}</Button>
          </Group>
        </Stack>
      </Card>
    </Center>
  );
}
