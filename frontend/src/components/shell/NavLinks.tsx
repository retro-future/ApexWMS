"use client";

import { Box, NavLink, Stack, Text } from "@mantine/core";
import {
  IconBuildingWarehouse,
  IconChartBar,
  IconClipboardList,
  IconLayoutDashboard,
  IconMapPin,
  IconPackageImport,
  IconReceipt,
  IconSettings,
  IconTruck,
  IconUsers,
  IconUsersGroup,
} from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useCan } from "@/components/MeProvider";
import { Permission } from "@/lib/permissions";

type Item = {
  href: string;
  label: string;
  icon: React.ElementType;
  permission?: string;
};

export function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const t = useTranslations("nav");
  const can = useCan();
  const pathname = usePathname();

  const sections: { title?: string; items: Item[] }[] = [
    {
      items: [
        { href: "/", label: t("dashboard"), icon: IconLayoutDashboard },
      ],
    },
    {
      title: t("catalog"),
      items: [
        {
          href: "/products",
          label: t("products"),
          icon: IconBuildingWarehouse,
          permission: Permission.Catalog.View,
        },
        {
          href: "/locations",
          label: t("locations"),
          icon: IconMapPin,
          permission: Permission.Location.View,
        },
        {
          href: "/suppliers",
          label: t("suppliers"),
          icon: IconTruck,
          permission: Permission.Catalog.View,
        },
        {
          href: "/customers",
          label: t("customers"),
          icon: IconUsersGroup,
          permission: Permission.Customer.View,
        },
      ],
    },
    {
      title: t("inbound"),
      items: [
        {
          href: "/purchase-orders",
          label: t("purchaseOrders"),
          icon: IconClipboardList,
          permission: Permission.PurchaseOrder.View,
        },
        {
          href: "/receipts",
          label: t("receipts"),
          icon: IconPackageImport,
          permission: Permission.Receiving.View,
        },
      ],
    },
    {
      title: t("outbound"),
      items: [
        {
          href: "/invoices",
          label: t("invoices"),
          icon: IconReceipt,
          permission: Permission.Sales.View,
        },
      ],
    },
    {
      title: t("reports"),
      items: [
        {
          href: "/reports/price-deviations",
          label: t("priceDeviations"),
          icon: IconChartBar,
          permission: Permission.Reporting.View,
        },
      ],
    },
    {
      title: t("administration"),
      items: [
        {
          href: "/staff",
          label: t("staff"),
          icon: IconUsers,
          permission: Permission.Users.View,
        },
        {
          href: "/settings",
          label: t("settings"),
          icon: IconSettings,
          permission: Permission.TenantSettings.View,
        },
      ],
    },
  ];

  return (
    <Stack gap="lg">
      {sections.map((section, index) => {
        const visible = section.items.filter(
          (item) => !item.permission || can(item.permission),
        );
        if (visible.length === 0) return null;

        return (
          <Box key={section.title ?? index}>
            {section.title && (
              <Text
                size="xs"
                fw={600}
                c="dimmed"
                tt="uppercase"
                mb="2xs"
                px="xs"
              >
                {section.title}
              </Text>
            )}
            {visible.map((item) => (
              <NavLink
                key={item.href}
                component={Link}
                href={item.href}
                label={item.label}
                onClick={onNavigate}
                active={
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href)
                }
                leftSection={<item.icon size={18} stroke={1.5} />}
              />
            ))}
          </Box>
        );
      })}
    </Stack>
  );
}
