"use client";

import {
  Anchor,
  Badge,
  Button,
  Checkbox,
  NumberInput,
  Select,
  Table,
  Text,
} from "@mantine/core";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { BulkRepriceModal } from "@/app/(app)/reports/BulkRepriceModal";
import { ListShell, SELECT_COLUMN_WIDTH } from "@/components/ListShell";
import { useCan } from "@/components/MeProvider";
import { useDateFormat } from "@/hooks/use-date-format";
import { useLocationLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { formatMoney } from "@/lib/money";
import { Permission } from "@/lib/permissions";
import type { AgeingRow, AgeingSort } from "@/lib/types";

/**
 * FR-9.4: what has been sitting too long, and how hard it has been pushed.
 *
 * The markdown count is the column the report is really for: a used handset
 * cut twice that is still on the shelf is the sharpest form of dead stock.
 * Cost and implied margin are absent without `Permission.Cost.View`, and the
 * rest of the row still reads without them.
 *
 * Rows are selectable so a run of dead stock is marked down in one call
 * (FR-2.21) rather than one page visit at a time.
 */
export function AgeingList() {
  const t = useTranslations("reports");
  const tDoc = useTranslations("documents");
  const tUnits = useTranslations("deviceUnits");
  const tCommon = useTranslations("common");
  const { formatDate } = useDateFormat();
  const can = useCan();

  const locations = useLocationLookup();

  const [days, setDays] = useState(30);
  const [locationId, setLocationId] = useState<string | null>(null);
  const [sort, setSort] = useState<AgeingSort>("age");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string[]>([]);
  const [pricing, setPricing] = useState(false);

  const reset = makePageReset(setPage);

  const query = useResourceList<AgeingRow>("reports/ageing", {
    page,
    days,
    sort,
    locationId: locationId ?? undefined,
  });

  const rows = query.data?.items ?? [];
  const showCost = rows.some((row) => row.acquisitionCost !== undefined);
  const canPrice = can(Permission.Pricing.Set);

  function toggle(id: string) {
    setSelected((current) =>
      current.includes(id) ? current.filter((one) => one !== id) : [...current, id],
    );
  }

  return (
    <>
      <ListShell
        title={t("ageingTitle")}
        subtitle={t("ageingSubtitle")}
        action={
          canPrice && (
            <Button disabled={selected.length === 0} onClick={() => setPricing(true)}>
              {t("priceSelected", { count: selected.length })}
            </Button>
          )
        }
        filters={
          <>
            <NumberInput
              label={t("olderThan")}
              value={days}
              onChange={(value) => reset(setDays)(Number(value) || 0)}
              min={0}
              w={{ base: "100%", sm: 140 }}
            />
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
            <Select
              label={t("sortBy")}
              value={sort}
              onChange={(value) => reset(setSort)((value ?? "age") as AgeingSort)}
              data={(["age", "markdowns"] as AgeingSort[]).map((key) => ({
                value: key,
                label: t(`ageingSort.${key}`),
              }))}
              w={{ base: "100%", sm: 180 }}
            />
          </>
        }
        head={
          <Table.Tr>
            {canPrice && <Table.Th w={SELECT_COLUMN_WIDTH} />}
            <Table.Th>{t("handset")}</Table.Th>
            <Table.Th>{t("filterLocation")}</Table.Th>
            <Table.Th>{t("daysInStock")}</Table.Th>
            <Table.Th>{tUnits("askingPrice")}</Table.Th>
            <Table.Th>{t("markdowns")}</Table.Th>
            {showCost && (
              <>
                <Table.Th>{tUnits("acquisitionCost")}</Table.Th>
                <Table.Th>{t("impliedMargin")}</Table.Th>
              </>
            )}
          </Table.Tr>
        }
        isLoading={query.isLoading}
        error={query.error}
        isEmpty={rows.length === 0}
        emptyMessage={t("noAgeing")}
        total={query.data?.totalItems ?? 0}
        page={page}
        pagesCount={query.data?.pagesCount ?? 0}
        onPageChange={setPage}
      >
        {rows.map((row) => (
          <Table.Tr key={row.deviceUnitId}>
            {canPrice && (
              <Table.Td>
                <Checkbox
                  aria-label={row.imei}
                  checked={selected.includes(row.deviceUnitId)}
                  onChange={() => toggle(row.deviceUnitId)}
                />
              </Table.Td>
            )}
            <Table.Td>
              <Anchor component={Link} href={`/device-units/${row.deviceUnitId}`} fw={500}>
                {row.productName}
              </Anchor>
              <Text size="xs" c="dimmed" ff="monospace">
                {row.imei}
              </Text>
              <Badge size="xs" variant="light" mt="3xs">
                {tDoc(`condition.${row.condition}`)}
              </Badge>
            </Table.Td>
            <Table.Td>
              <Text size="sm">{row.locationName ?? tCommon("none")}</Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm" fw={600}>
                {row.daysInStock}
              </Text>
              <Text size="xs" c="dimmed">
                {formatDate(row.since)}
              </Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm">
                {row.askingPrice === null
                  ? tCommon("none")
                  : formatMoney(row.askingPrice)}
              </Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm" fw={row.markdownCount > 0 ? 600 : undefined}>
                {row.markdownCount}
              </Text>
            </Table.Td>
            {showCost && (
              <>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {row.acquisitionCost === null ||
                    row.acquisitionCost === undefined
                      ? tCommon("none")
                      : formatMoney(row.acquisitionCost)}
                  </Text>
                </Table.Td>
                <Table.Td>
                  {row.impliedMargin === null ||
                  row.impliedMargin === undefined ? (
                    <Text size="sm" c="dimmed">
                      {tCommon("none")}
                    </Text>
                  ) : (
                    <Text size="sm" c={row.impliedMargin.minor < 0 ? "red" : "teal"}>
                      {formatMoney(row.impliedMargin)}
                    </Text>
                  )}
                </Table.Td>
              </>
            )}
          </Table.Tr>
        ))}
      </ListShell>
      {pricing && (
        <BulkRepriceModal
          deviceUnitIds={selected}
          onClose={() => setPricing(false)}
          onDone={() => setSelected([])}
        />
      )}
    </>
  );
}
