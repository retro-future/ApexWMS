"use client";

import { Anchor, Badge, Select, Table, Text } from "@mantine/core";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { DocumentLink } from "@/app/(app)/reports/DocumentLink";
import { DeviceStatusBadge } from "@/components/DeviceStatusBadge";
import { ListShell } from "@/components/ListShell";
import { ProductSelect } from "@/components/ProductSelect";
import { useDateFormat } from "@/hooks/use-date-format";
import { useLocationLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { formatMoney } from "@/lib/money";
import type {
  DeviceCondition,
  DeviceInventoryRow,
  DeviceInventorySort,
  DeviceInventoryStatusFilter,
} from "@/lib/types";

const STATUSES: DeviceInventoryStatusFilter[] = [
  "in_stock",
  "sold",
  "customer_returned",
  "returned_to_supplier",
  "written_off",
  "receipt_cancelled",
];
const CONDITIONS: DeviceCondition[] = ["new", "refurbished", "used"];
const SORTS: DeviceInventorySort[] = ["received", "imei", "status"];

/**
 * Browse every handset by IMEI, filterable by product, location, status and
 * condition. The count screen `/reports/stock-on-hand` answers "how many";
 * this one answers "which ones and where". Cost and margin columns are absent
 * without `Permission.Cost.View`.
 */
export function DeviceInventoryList() {
  const t = useTranslations("reports");
  const tDoc = useTranslations("documents");
  const tUnits = useTranslations("deviceUnits");
  const tCommon = useTranslations("common");
  const { formatDate } = useDateFormat();

  const locations = useLocationLookup();

  const [productId, setProductId] = useState<string | null>(null);
  const [locationId, setLocationId] = useState<string | null>(null);
  const [status, setStatus] = useState<DeviceInventoryStatusFilter | null>(null);
  const [condition, setCondition] = useState<DeviceCondition | null>(null);
  const [sort, setSort] = useState<DeviceInventorySort>("received");
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<DeviceInventoryRow>("reports/device-units", {
    page,
    sort,
    productId: productId ?? undefined,
    locationId: locationId ?? undefined,
    status: status ?? undefined,
    condition: condition ?? undefined,
  });

  const rows = query.data?.items ?? [];
  const showCost = rows.some((row) => row.acquisitionCost !== undefined);

  return (
    <ListShell
      title={t("deviceInventoryTitle")}
      subtitle={t("deviceInventorySubtitle")}
      filters={
        <>
          <ProductSelect
            value={productId}
            onChange={(product) => reset(setProductId)(product?.id ?? null)}
            placeholder={t("filterProduct")}
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
            aria-label={t("filterStatus")}
            value={status}
            onChange={(value) =>
              reset(setStatus)((value as DeviceInventoryStatusFilter) ?? null)
            }
            placeholder={t("filterStatus")}
            clearable
            w={{ base: "100%", sm: 200 }}
            data={STATUSES.map((key) => ({
              value: key,
              label: t(`deviceStatusFilter.${key}`),
            }))}
          />
          <Select
            value={condition}
            onChange={(value) =>
              reset(setCondition)((value as DeviceCondition) ?? null)
            }
            placeholder={t("filterCondition")}
            clearable
            w={{ base: "100%", sm: 160 }}
            data={CONDITIONS.map((key) => ({
              value: key,
              label: tDoc(`condition.${key}`),
            }))}
          />
          <Select
            label={t("sortBy")}
            value={sort}
            onChange={(value) =>
              reset(setSort)((value ?? "received") as DeviceInventorySort)
            }
            data={SORTS.map((key) => ({
              value: key,
              label: t(`deviceInventorySort.${key}`),
            }))}
            w={{ base: "100%", sm: 180 }}
          />
        </>
      }
      head={
        <Table.Tr>
          <Table.Th>{t("handset")}</Table.Th>
          <Table.Th>{t("filterStatus")}</Table.Th>
          <Table.Th>{t("filterLocation")}</Table.Th>
          <Table.Th>{t("daysInStock")}</Table.Th>
          <Table.Th>{tUnits("resolvedPrice")}</Table.Th>
          {showCost && (
            <>
              <Table.Th>{tUnits("acquisitionCost")}</Table.Th>
              <Table.Th>{t("impliedMargin")}</Table.Th>
            </>
          )}
          <Table.Th>{t("sourceDocument")}</Table.Th>
        </Table.Tr>
      }
      isLoading={query.isLoading}
      error={query.error}
      isEmpty={rows.length === 0}
      emptyMessage={t("noDeviceInventory")}
      total={query.data?.totalItems ?? 0}
      page={page}
      pagesCount={query.data?.pagesCount ?? 0}
      onPageChange={setPage}
    >
      {rows.map((row) => (
        <Table.Tr key={row.deviceUnitId}>
          <Table.Td>
            <Anchor
              component={Link}
              href={`/device-units/${row.deviceUnitId}`}
              fw={500}
            >
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
            <DeviceStatusBadge
              status={row.status}
              returned={row.wasCustomerReturned}
            />
          </Table.Td>
          <Table.Td>
            <Text size="sm">{row.locationName ?? tCommon("none")}</Text>
          </Table.Td>
          <Table.Td>
            {row.status === "in_stock" || row.status === "reserved" ? (
              <>
                <Text size="sm" fw={600}>
                  {row.daysInStock}
                </Text>
                <Text size="xs" c="dimmed">
                  {formatDate(row.since)}
                </Text>
              </>
            ) : (
              <Text size="sm" c="dimmed">
                {tCommon("none")}
              </Text>
            )}
          </Table.Td>
          <Table.Td>
            <Text size="sm">
              {row.resolvedPrice == null
                ? tCommon("none")
                : formatMoney(row.resolvedPrice)}
            </Text>
          </Table.Td>
          {showCost && (
            <>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  {row.acquisitionCost
                    ? formatMoney(row.acquisitionCost)
                    : tCommon("none")}
                </Text>
              </Table.Td>
              <Table.Td>
                {row.impliedMargin ? (
                  <Text
                    size="sm"
                    c={row.impliedMargin.minor < 0 ? "red" : "teal"}
                  >
                    {formatMoney(row.impliedMargin)}
                  </Text>
                ) : (
                  <Text size="sm" c="dimmed">
                    {tCommon("none")}
                  </Text>
                )}
              </Table.Td>
            </>
          )}
          <Table.Td>
            {row.sourceDocumentType && row.sourceDocumentId ? (
              <DocumentLink
                documentType={row.sourceDocumentType}
                documentId={row.sourceDocumentId}
                documentNumber={null}
              />
            ) : (
              <Text size="sm" c="dimmed">
                {tCommon("none")}
              </Text>
            )}
          </Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}
