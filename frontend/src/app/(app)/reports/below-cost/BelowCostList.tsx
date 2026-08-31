"use client";

import { Anchor, Select, Table, Text } from "@mantine/core";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { ListShell } from "@/components/ListShell";
import { useLocationLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { formatMoney } from "@/lib/money";
import type { BelowCostRow } from "@/lib/types";

/**
 * Accessories whose average unit cost has reached their catalog price. Each row
 * carries its own currency, so the money cells are formatted from the minor
 * amounts rather than trusting a pre-formatted string.
 */
export function BelowCostList() {
  const t = useTranslations("reports");

  const locations = useLocationLookup();

  const [locationId, setLocationId] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<BelowCostRow>("reports/below-cost", {
    page,
    locationId: locationId ?? undefined,
  });

  const rows = query.data?.items ?? [];

  return (
    <ListShell
      title={t("belowCostTitle")}
      subtitle={t("belowCostSubtitle")}
      filters={
        <Select
          value={locationId}
          onChange={reset(setLocationId)}
          placeholder={t("filterLocation")}
          clearable
          searchable
          w={{ base: "100%", sm: 200 }}
          data={locations.all.map((location) => ({
            value: location.id,
            label: location.name,
          }))}
        />
      }
      head={
        <Table.Tr>
          <Table.Th>{t("filterProduct")}</Table.Th>
          <Table.Th>{t("filterLocation")}</Table.Th>
          <Table.Th>{t("quantityOnHand")}</Table.Th>
          <Table.Th>{t("catalogPrice")}</Table.Th>
          <Table.Th>{t("averageCost")}</Table.Th>
          <Table.Th>{t("shortfall")}</Table.Th>
        </Table.Tr>
      }
      isLoading={query.isLoading}
      error={query.error}
      isEmpty={rows.length === 0}
      emptyMessage={t("noBelowCost")}
      total={query.data?.totalItems ?? 0}
      page={page}
      pagesCount={query.data?.pagesCount ?? 0}
      onPageChange={setPage}
    >
      {rows.map((row) => (
        <Table.Tr key={`${row.productId}:${row.locationId}`}>
          <Table.Td>
            <Anchor component={Link} href={`/products/${row.productId}`} fw={500}>
              {row.productName}
            </Anchor>
            <Text size="xs" c="dimmed" ff="monospace">
              {row.sku}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">{row.locationName}</Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">{row.quantity}</Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">{formatMoney(row.catalogPriceMinor, row.currency)}</Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">
              {formatMoney(row.averageUnitCostMinor, row.currency)}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm" c="red">
              {formatMoney(row.shortfallMinor, row.currency)}
            </Text>
          </Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}
