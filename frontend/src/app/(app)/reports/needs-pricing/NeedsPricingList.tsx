"use client";

import { Anchor, Badge, Button, Checkbox, Select, Table, Text } from "@mantine/core";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { BulkRepriceModal } from "@/app/(app)/reports/BulkRepriceModal";
import { ListShell, SELECT_COLUMN_WIDTH } from "@/components/ListShell";
import { useCan } from "@/components/MeProvider";
import { useDateFormat } from "@/hooks/use-date-format";
import { useLocationLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { Permission } from "@/lib/permissions";
import type { NeedsPricingRow } from "@/lib/types";

/**
 * FR-9.6: everything in stock that cannot be sold for want of a price.
 *
 * The list exists so a price is set here rather than at the counter with a
 * customer standing there, so the rows are selectable and priced in one
 * call (FR-2.21) instead of one page visit each.
 */
export function NeedsPricingList() {
  const t = useTranslations("reports");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { formatDate } = useDateFormat();
  const can = useCan();

  const locations = useLocationLookup();

  const [locationId, setLocationId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string[]>([]);
  const [pricing, setPricing] = useState(false);

  const reset = makePageReset(setPage);

  const query = useResourceList<NeedsPricingRow>("reports/needs-pricing", {
    page,
    locationId: locationId ?? undefined,
  });

  const rows = query.data?.items ?? [];
  const canPrice = can(Permission.Pricing.Set);

  function toggle(id: string) {
    setSelected((current) =>
      current.includes(id) ? current.filter((one) => one !== id) : [...current, id],
    );
  }

  return (
    <>
      <ListShell
        title={t("needsPricingTitle")}
        subtitle={t("needsPricingSubtitle")}
        action={
          canPrice && (
            <Button disabled={selected.length === 0} onClick={() => setPricing(true)}>
              {t("priceSelected", { count: selected.length })}
            </Button>
          )
        }
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
            {canPrice && <Table.Th w={SELECT_COLUMN_WIDTH} />}
            <Table.Th>{t("handset")}</Table.Th>
            <Table.Th>{t("filterLocation")}</Table.Th>
            <Table.Th>{t("daysUnpriced")}</Table.Th>
            <Table.Th>{tDoc("reason")}</Table.Th>
          </Table.Tr>
        }
        isLoading={query.isLoading}
        error={query.error}
        isEmpty={rows.length === 0}
        emptyMessage={t("noNeedsPricing")}
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
                {row.daysUnpriced}
              </Text>
              <Text size="xs" c="dimmed">
                {formatDate(row.since)}
              </Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm">{t(`needsPricingReason.${row.reason}`)}</Text>
            </Table.Td>
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
