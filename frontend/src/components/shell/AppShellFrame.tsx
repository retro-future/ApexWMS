"use client";

import { AppShell, Burger, Group, Text } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";

import { MeProvider } from "@/components/MeProvider";
import { LanguageSwitcher } from "@/components/shell/LanguageSwitcher";
import { NavLinks } from "@/components/shell/NavLinks";
import { ScanBar } from "@/components/shell/ScanBar";
import { StaleRateReminder } from "@/components/shell/StaleRateReminder";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import { UserMenu } from "@/components/shell/UserMenu";
import type { Me } from "@/lib/types";

import classes from "./AppShellFrame.module.css";

export function AppShellFrame({
  me,
  children,
}: {
  me: Me;
  children: React.ReactNode;
}) {
  const [opened, { toggle, close }] = useDisclosure(false);

  return (
    <MeProvider me={me}>
      <StaleRateReminder />
      <AppShell
        header={{ height: 60 }}
        navbar={{
          width: 260,
          breakpoint: "sm",
          collapsed: { mobile: !opened },
        }}
        padding="md"
      >
        <AppShell.Header>
          <Group h="100%" px="md" justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap">
              <Burger
                opened={opened}
                onClick={toggle}
                hiddenFrom="sm"
                size="sm"
              />
              <Text fw={700} size="lg">
                ApexWMS
              </Text>
            </Group>
            <Group gap="xs" wrap="nowrap">
              <ScanBar />
              <LanguageSwitcher />
              <ThemeToggle />
              <UserMenu />
            </Group>
          </Group>
        </AppShell.Header>

        <AppShell.Navbar p="md" className={classes.navbar}>
          <NavLinks onNavigate={close} />
        </AppShell.Navbar>

        <AppShell.Main>{children}</AppShell.Main>
      </AppShell>
    </MeProvider>
  );
}
