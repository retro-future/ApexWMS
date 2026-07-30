"use client";

import { Alert, Button, Card, Center, Code, Group, Stack, Text, Title } from "@mantine/core";
import { IconInfoCircle, IconLogout } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";

import type { Me } from "@/lib/types";

/**
 * A platform operator's token carries no tenant claim (PRD §3.3), so every
 * store-scoped endpoint would answer 400 "no tenant named". Rather than show
 * a full navigation that 400s everywhere, say plainly that this account has
 * no store attached.
 */
export function PlatformOperatorNotice({ me }: { me: Me }) {
  const t = useTranslations("auth");
  const tNav = useTranslations("nav");
  const router = useRouter();

  async function signOut() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  return (
    <Center mih="100dvh" p="md">
      <Card withBorder shadow="sm" padding="xl" radius="md" maw={560}>
        <Stack gap="md">
          <Title order={3}>{t("platformOperatorTitle")}</Title>
          <Alert
            variant="light"
            color="blue"
            icon={<IconInfoCircle size={18} />}
          >
            {t("platformOperatorBody")}
          </Alert>
          <Text size="sm" c="dimmed">
            {me.email}
          </Text>
          <Code block>
            {[
              "uv run apexwms list-tenants",
              "uv run apexwms create-tenant --name '…' --slug '…' \\",
              "    --owner-email '…' --owner-name '…'",
            ].join("\n")}
          </Code>
          <Group justify="flex-end">
            <Button
              variant="light"
              color="red"
              leftSection={<IconLogout size={16} />}
              onClick={signOut}
            >
              {tNav("signOut")}
            </Button>
          </Group>
        </Stack>
      </Card>
    </Center>
  );
}
