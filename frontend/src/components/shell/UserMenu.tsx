"use client";

import { Avatar, Badge, Group, Menu, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconKey, IconLogout } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";

import { useMe } from "@/components/MeProvider";
import { roleLabelKey } from "@/lib/roles";

export function UserMenu() {
  const t = useTranslations("nav");
  const tStaff = useTranslations("staff.roles");
  const me = useMe();
  const router = useRouter();

  async function signOut() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  const initials = me.fullName
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <Menu shadow="md" width={240} position="bottom-end">
      <Menu.Target>
        <UnstyledButton aria-label={me.fullName}>
          <Avatar color="brand" radius="xl" size={34}>
            {initials || "?"}
          </Avatar>
        </UnstyledButton>
      </Menu.Target>

      <Menu.Dropdown>
        <Menu.Label>
          <Stack gap="3xs">
            <Text size="sm" fw={600}>
              {me.fullName}
            </Text>
            <Text size="xs" c="dimmed">
              {me.email}
            </Text>
            {me.role && (
              <Group gap="xs" mt="2xs">
                <Badge size="xs" variant="light">
                  {tStaff(roleLabelKey(me.role))}
                </Badge>
              </Group>
            )}
          </Stack>
        </Menu.Label>

        <Menu.Divider />

        <Menu.Item
          leftSection={<IconKey size={16} />}
          onClick={() => router.push("/change-password")}
        >
          {t("changePassword")}
        </Menu.Item>
        <Menu.Item
          color="red"
          leftSection={<IconLogout size={16} />}
          onClick={signOut}
        >
          {t("signOut")}
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}
