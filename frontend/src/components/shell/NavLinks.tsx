"use client";

import { Box, NavLink, Stack, Text } from "@mantine/core";
import {
  IconArrowBackUp,
  IconArrowsExchange,
  IconBuildingWarehouse,
  IconCalendarStats,
  IconChartBar,
  IconChartLine,
  IconChecklist,
  IconClipboardList,
  IconCoins,
  IconCreditCard,
  IconDeviceMobile,
  IconHourglass,
  IconLayoutDashboard,
  IconMapPin,
  IconPackageImport,
  IconReceipt,
  IconRoute,
  IconScale,
  IconSettings,
  IconStack2,
  IconTag,
  IconTrashX,
  IconTrendingDown,
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
        {
          href: "/device-units",
          label: t("devices"),
          icon: IconDeviceMobile,
          permission: Permission.Reporting.View,
        },
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
        {
          href: "/credit-companies",
          label: t("creditCompanies"),
          icon: IconCreditCard,
          permission: Permission.CreditCompany.View,
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
        {
          href: "/customer-returns",
          label: t("customerReturns"),
          icon: IconArrowBackUp,
          permission: Permission.CustomerReturn.View,
        },
      ],
    },
    {
      title: t("adjustments"),
      items: [
        {
          href: "/stock-counts",
          label: t("stockCounts"),
          icon: IconChecklist,
          permission: Permission.StockCount.Run,
        },
        {
          href: "/write-offs",
          label: t("writeOffs"),
          icon: IconTrashX,
          permission: Permission.WriteOff.Manage,
        },
        {
          href: "/supplier-returns",
          label: t("supplierReturns"),
          icon: IconArrowBackUp,
          permission: Permission.SupplierReturn.View,
        },
      ],
    },
    {
      title: t("reports"),
      items: [
        {
          href: "/reports/stock-on-hand",
          label: t("stockOnHand"),
          icon: IconStack2,
          permission: Permission.Reporting.View,
        },
        {
          href: "/reports/trace",
          label: t("trace"),
          icon: IconRoute,
          permission: Permission.Catalog.View,
        },
        {
          href: "/reports/movements",
          label: t("movements"),
          icon: IconArrowsExchange,
          permission: Permission.Reporting.View,
        },
        {
          href: "/reports/sales-summary",
          label: t("salesSummary"),
          icon: IconChartLine,
          permission: Permission.Reporting.View,
        },
        {
          href: "/reports/ageing",
          label: t("ageing"),
          icon: IconHourglass,
          permission: Permission.Reporting.View,
        },
        {
          href: "/reports/needs-pricing",
          label: t("needsPricing"),
          icon: IconTag,
          permission: Permission.Reporting.View,
        },
        {
          href: "/reports/below-cost",
          label: t("belowCost"),
          icon: IconTrendingDown,
          permission: Permission.Reporting.View,
        },
        {
          href: "/reports/financial-ledger",
          label: t("financialLedger"),
          icon: IconCoins,
          permission: Permission.FinancialLedger.View,
        },
        {
          href: "/reports/month-end",
          label: t("monthEnd"),
          icon: IconCalendarStats,
          permission: Permission.FinancialLedger.View,
        },
        {
          href: "/reports/price-deviations",
          label: t("priceDeviations"),
          icon: IconChartBar,
          permission: Permission.Reporting.View,
        },
        {
          href: "/reports/debtors",
          label: t("debtors"),
          icon: IconScale,
          permission: Permission.CustomerAccount.ViewAll,
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
