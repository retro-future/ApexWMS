"use client";

import { Anchor, Select, Table, Text, TextInput } from "@mantine/core";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { DocumentLink } from "@/app/(app)/reports/DocumentLink";
import { ListShell } from "@/components/ListShell";
import { ProductSelect } from "@/components/ProductSelect";
import { useDateFormat } from "@/hooks/use-date-format";
import { useEmployeeLookup, useLocationLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import type { MovementRow, MovementType } from "@/lib/types";

const MOVEMENT_TYPES: MovementType[] = [
  "receipt",
  "sale",
  "supplier_return",
  "count_adjustment",
  "write_off",
];

/**
 * FR-9.5: the raw stock ledger, filterable and complete.
 *
 * Nothing is excluded — a reversal sits beside the movement it reverses,
 * because both happened. The rows count goods and carry no money: what the
 * same event did to the till is the financial ledger (FR-10.3).
 */
export function MovementLogList() {
  const t = useTranslations("reports");
  const tDoc = useTranslations("documents");
  const { formatDateTime } = useDateFormat();

  const locations = useLocationLookup();
  const employees = useEmployeeLookup();

  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [productId, setProductId] = useState<string | null>(null);
  const [locationId, setLocationId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [movementType, setMovementType] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<MovementRow>("reports/movements", {
    page,
    fromDate: from ? new Date(from).toISOString() : undefined,
    // Through the end of the chosen day, not its first instant.
    toDate: to ? new Date(`${to}T23:59:59.999Z`).toISOString() : undefined,
    productId: productId ?? undefined,
    locationId: locationId ?? undefined,
    userId: userId ?? undefined,
    movementType: movementType ?? undefined,
  });

  const rows = query.data?.items ?? [];

  return (
    <ListShell
      title={t("movementsTitle")}
      subtitle={t("movementsSubtitle")}
      filters={
        <>
          <TextInput
            type="date"
            label={t("from")}
            value={from}
            onChange={(event) => reset(setFrom)(event.currentTarget.value)}
            w={{ base: "100%", sm: 160 }}
          />
          <TextInput
            type="date"
            label={t("to")}
            value={to}
            onChange={(event) => reset(setTo)(event.currentTarget.value)}
            w={{ base: "100%", sm: 160 }}
          />
          <Select
            value={movementType}
            onChange={reset(setMovementType)}
            placeholder={t("filterMovementType")}
            clearable
            w={{ base: "100%", sm: 200 }}
            data={MOVEMENT_TYPES.map((type) => ({
              value: type,
              label: t(`movementType.${type}`),
            }))}
          />
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
            value={userId}
            onChange={reset(setUserId)}
            placeholder={t("filterUser")}
            clearable
            searchable
            w={{ base: "100%", sm: 200 }}
            data={employees.all.map((employee) => ({
              value: employee.id,
              label: employee.fullName,
            }))}
          />
        </>
      }
      head={
        <Table.Tr>
          <Table.Th>{t("date")}</Table.Th>
          <Table.Th>{t("movement")}</Table.Th>
          <Table.Th>{tDoc("quantity")}</Table.Th>
          <Table.Th>{tDoc("product")}</Table.Th>
          <Table.Th>{t("filterLocation")}</Table.Th>
          <Table.Th>{t("document")}</Table.Th>
          <Table.Th>{t("filterUser")}</Table.Th>
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
        <Table.Tr key={row.id}>
          <Table.Td>
            <Text size="sm">{formatDateTime(row.occurredAt)}</Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">{t(`movementType.${row.movementType}`)}</Text>
            {row.note && (
              <Text size="xs" c="dimmed">
                {row.note}
              </Text>
            )}
          </Table.Td>
          <Table.Td>
            {/* Signed: a reversal keeps its type and flips the sign (§4.3). */}
            <Text size="sm" fw={600} c={row.quantityDelta < 0 ? "red" : "teal"}>
              {row.quantityDelta > 0 ? "+" : ""}
              {row.quantityDelta}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">{row.productName}</Text>
            {row.imei && row.deviceUnitId ? (
              <Anchor
                component={Link}
                href={`/device-units/${row.deviceUnitId}`}
                size="xs"
                ff="monospace"
              >
                {row.imei}
              </Anchor>
            ) : (
              <Text size="xs" c="dimmed">
                {row.sku}
              </Text>
            )}
          </Table.Td>
          <Table.Td>
            <Text size="sm">{row.locationName}</Text>
          </Table.Td>
          <Table.Td>
            <DocumentLink
              documentType={row.documentType}
              documentId={row.documentId}
              documentNumber={row.documentNumber}
            />
          </Table.Td>
          <Table.Td>
            <Text size="sm">{row.userName ?? t("unattributed")}</Text>
          </Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}
