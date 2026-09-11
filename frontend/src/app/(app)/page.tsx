"use client";

import {
  Button,
  Card,
  Group,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import {
  IconBarcode,
  IconBuildingWarehouse,
  IconClipboardList,
  IconMapPin,
  IconPackageImport,
  IconTruck,
  IconUsersGroup,
} from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { useCan, useMe } from "@/components/MeProvider";
import { useResourceList } from "@/hooks/use-resource";
import { useScanLookup } from "@/hooks/use-scan-lookup";
import { Permission } from "@/lib/permissions";

import { RatesCard } from "./RatesCard";

/**
 * Deliberately modest: counts of what exists and a way into it. Anything
 * resembling a real figure — stock value, margin, what sold today — is
 * reporting (M8) and would be guesswork assembled from list endpoints here.
 */
export default function DashboardPage() {
  const t = useTranslations("dashboard");
  const tNav = useTranslations("nav");
  const me = useMe();
  const can = useCan();

  /** Work in progress first: a draft document is something to go and finish. */
  const inbound = [
    {
      resource: "purchase-orders",
      href: "/purchase-orders?status=draft",
      label: t("draftOrders"),
      icon: IconClipboardList,
      permission: Permission.PurchaseOrder.View,
    },
    {
      resource: "receipts",
      href: "/receipts?status=draft",
      label: t("draftReceipts"),
      icon: IconPackageImport,
      permission: Permission.Receiving.View,
    },
  ].filter((card) => can(card.permission));

  const cards = [
    {
      resource: "products",
      href: "/products",
      label: tNav("products"),
      icon: IconBuildingWarehouse,
      permission: Permission.Catalog.View,
    },
    {
      resource: "locations",
      href: "/locations",
      label: tNav("locations"),
      icon: IconMapPin,
      permission: Permission.Location.View,
    },
    {
      resource: "suppliers",
      href: "/suppliers",
      label: tNav("suppliers"),
      icon: IconTruck,
      permission: Permission.Catalog.View,
    },
    {
      resource: "customers",
      href: "/customers",
      label: tNav("customers"),
      icon: IconUsersGroup,
      permission: Permission.Customer.View,
    },
  ].filter((card) => can(card.permission));

  return (
    <Stack gap="lg">
      <Stack gap="3xs">
        <Title order={2}>
          {t("welcome", { name: me.fullName.split(" ")[0] })}
        </Title>
        <Text size="sm" c="dimmed">
          {t("subtitle")}
        </Text>
      </Stack>

      <RatesCard />

      <MobileScanCard />

      {inbound.length > 0 && (
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          {inbound.map((card) => (
            <CountCard
              key={card.resource}
              resource={card.resource}
              href={card.href}
              label={card.label}
              icon={card.icon}
              filters={{ status: "draft" }}
            />
          ))}
        </SimpleGrid>
      )}

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        {cards.map((card) => (
          <CountCard
            key={card.resource}
            resource={card.resource}
            href={card.href}
            label={card.label}
            icon={card.icon}
            filters={{ isActive: true }}
          />
        ))}
      </SimpleGrid>
    </Stack>
  );
}

/**
 * The header's ScanBar hides its text field below the `sm` breakpoint and
 * offers only a camera trigger there (§7). A phone typing off a Bluetooth
 * wedge or a manually keyed IMEI still needs somewhere to land it, so the
 * dashboard carries the same lookup as a full-width mobile card.
 */
function MobileScanCard() {
  const t = useTranslations("scan");
  const can = useCan();
  const [code, setCode] = useState("");
  const lookup = useScanLookup();

  if (!can(Permission.Scan.Lookup)) return null;

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const scanned = code.trim();
    if (scanned) lookup.mutate(scanned, { onSuccess: () => setCode("") });
  }

  return (
    <Card hiddenFrom="sm" withBorder radius="md" padding="lg">
      <form onSubmit={submit}>
        <Stack gap="sm">
          <TextInput
            value={code}
            onChange={(event) => setCode(event.currentTarget.value)}
            placeholder={t("placeholder")}
            aria-label={t("placeholder")}
            leftSection={<IconBarcode size={18} stroke={1.5} />}
            autoComplete="off"
            spellCheck={false}
          />
          <Button type="submit" fullWidth loading={lookup.isPending}>
            {t("button")}
          </Button>
        </Stack>
      </form>
    </Card>
  );
}

function CountCard({
  resource,
  href,
  label,
  icon: Icon,
  filters,
}: {
  resource: string;
  href: string;
  label: string;
  icon: React.ElementType;
  /** Must match what the linked page shows, or the card disagrees with it. */
  filters: Record<string, string | boolean>;
}) {
  // pageSize 1: all we want from the list is its `totalItems`.
  const { data, isLoading } = useResourceList<unknown>(resource, {
    page: 1,
    pageSize: 1,
    ...filters,
  });

  return (
    <Card component={Link} href={href} withBorder radius="md" padding="lg">
      <Group justify="space-between" align="flex-start">
        <Stack gap="2xs">
          <Text size="sm" c="dimmed">
            {label}
          </Text>
          {isLoading ? (
            <Skeleton height={30} width={56} />
          ) : (
            <Text fw={700} fz="2xl" lh={1}>
              {data?.totalItems ?? 0}
            </Text>
          )}
        </Stack>
        <Icon size={22} stroke={1.5} opacity={0.6} />
      </Group>
    </Card>
  );
}
