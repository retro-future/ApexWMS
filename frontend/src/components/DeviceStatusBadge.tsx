"use client";

import { Badge, Group } from "@mantine/core";
import { useTranslations } from "next-intl";

import type { DeviceStatus } from "@/lib/types";

/**
 * Where a handset is in its life (PRD §4.2). A customer-returned unit is
 * `in_stock` again, so `returned` is passed alongside the status rather than
 * being one of its values.
 */
const COLOR: Record<DeviceStatus, string> = {
  in_stock: "teal",
  reserved: "blue",
  sold: "gray",
  returned_to_supplier: "yellow",
  written_off: "red",
  receipt_cancelled: "gray",
};

export function DeviceStatusBadge({
  status,
  returned = false,
}: {
  status: DeviceStatus;
  returned?: boolean;
}) {
  const t = useTranslations("documents");
  return (
    <Group gap="3xs" wrap="nowrap">
      <Badge size="sm" variant="light" color={COLOR[status]}>
        {t(`deviceStatus.${status}`)}
      </Badge>
      {returned && (
        <Badge size="sm" variant="outline" color="yellow">
          {t("deviceStatus.customer_returned")}
        </Badge>
      )}
    </Group>
  );
}
