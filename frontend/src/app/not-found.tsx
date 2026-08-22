import { Button, Card, Center, Stack, Title } from "@mantine/core";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

export default async function NotFound() {
  const t = await getTranslations("errors");
  const tNav = await getTranslations("nav");

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
