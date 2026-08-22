"use client";

import { Button, Card, Center, Stack, Title } from "@mantine/core";
import { useTranslations } from "next-intl";
import Link from "next/link";

export default function NotFound() {
  const t = useTranslations("errors");
  const tNav = useTranslations("nav");

  return (
    <Center mih="100dvh" p="md">
      <Card withBorder shadow="sm" padding="xl" radius="md" maw={480}>
        <Stack gap="lg" align="center">
          <Title order={3}>{t("notFound")}</Title>
          <Button component={Link} href="/">
            {tNav("dashboard")}
          </Button>
        </Stack>
      </Card>
    </Center>
  );
}
