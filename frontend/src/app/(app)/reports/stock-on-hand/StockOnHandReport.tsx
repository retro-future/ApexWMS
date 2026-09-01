"use client";

import { Anchor, Select, Table, Text, TextInput } from "@mantine/core";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { ListShell } from "@/components/ListShell";
import { ProductSelect } from "@/components/ProductSelect";
import { Subtotals } from "@/components/Subtotals";
import { useLocationLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import type { StockGroupBy, StockOnHandRow } from "@/lib/types";

/**
 * FR-9.1: what is on the shelves, grouped three ways.
 *
 * The cost column appears only when the payload carries one — without
 * `Permission.Cost.View` the server omits `costValue` rather than sending a
 * figure for a screen to hide (FR-1.7). It is a list of per-currency
 * subtotals, never one merged number.
 */
export function StockOnHandReport() {
  const t = useTranslations("reports");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");

  const locations = useLocationLookup();

  const [groupBy, setGroupBy] = useState<StockGroupBy>("location");
  const [locationId, setLocationId] = useState<string | null>(null);
  const [productId, setProductId] = useState<string | null>(null);
  const [brand, setBrand] = useState("");
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<StockOnHandRow>("reports/stock-on-hand", {
    page,
    groupBy,
    locationId: locationId ?? undefined,
    productId: productId ?? undefined,
    brand: brand || undefined,
  });

  const rows = query.data?.items ?? [];
  const showCost = rows.some((row) => row.costValue);

  return (
    <ListShell
      title={t("stockOnHandTitle")}
      subtitle={t("stockOnHandSubtitle")}
      filters={
        <>
          <Select
            label={t("groupBy")}
            value={groupBy}
            onChange={(value) => reset(setGroupBy)((value ?? "location") as StockGroupBy)}
            data={(["location", "product", "brand"] as StockGroupBy[]).map((key) => ({
              value: key,
              label: t(`groupByOption.${key}`),
            }))}
            w={{ base: "100%", sm: 180 }}
          />
          <Select
            label={t("filterLocation")}
            value={locationId}
            onChange={reset(setLocationId)}
            placeholder={tCommon("all")}
            clearable
            searchable
            w={{ base: "100%", sm: 200 }}
            data={locations.all.map((location) => ({
              value: location.id,
              label: location.name,
            }))}
          />
          <ProductSelect
            label={t("filterProduct")}
            value={productId}
            onChange={(product) => reset(setProductId)(product?.id ?? null)}
            placeholder={tCommon("all")}
          />
          <TextInput
            label={t("filterBrand")}
            value={brand}
            onChange={(event) => reset(setBrand)(event.currentTarget.value)}
            w={{ base: "100%", sm: 160 }}
          />
        </>
      }
      head={
        <Table.Tr>
          <Table.Th>{t(`groupByOption.${groupBy}`)}</Table.Th>
          <Table.Th>{tDoc("quantity")}</Table.Th>
          {showCost && <Table.Th>{t("costValue")}</Table.Th>}
        </Table.Tr>
      }
      isLoading={query.isLoading}
      error={query.error}
      isEmpty={rows.length === 0}
      total={query.data?.totalItems ?? 0}
      page={page}
      pagesCount={query.data?.pagesCount ?? 0}
      onPageChange={setPage}
    >
      {rows.map((row) => (
        <Table.Tr key={`${row.groupBy}-${row.key ?? row.label}`}>
          <Table.Td>
            {groupBy === "product" && row.key ? (
              <div>
                <Anchor component={Link} href={`/products/${row.key}`} fw={500}>
                  {row.label}
                </Anchor>
                {row.sku && (
                  <Text size="xs" c="dimmed">
                    {row.sku}
                  </Text>
                )}
              </div>
            ) : (
              <Text size="sm" fw={500}>
                {row.label || tCommon("none")}
              </Text>
            )}
          </Table.Td>
          <Table.Td>
            <Text size="sm" fw={600}>
              {row.quantity}
            </Text>
          </Table.Td>
          {showCost && (
            <Table.Td>
              <Subtotals subtotals={row.costValue ?? []} />
            </Table.Td>
          )}
        </Table.Tr>
      ))}
    </ListShell>
  );
}
