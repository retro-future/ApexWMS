"use client";

import { Anchor, Badge, Button, Select, Table, Text } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconPlus } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { DocumentStatusBadge } from "@/components/DocumentStatusBadge";
import { ListShell } from "@/components/ListShell";
import { useCan } from "@/components/MeProvider";
import { Subtotals } from "@/components/Subtotals";
import {
  useCustomerLookup,
  useLocationLookup,
  useSupplierLookup,
} from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { Permission } from "@/lib/permissions";
import { isSerial } from "@/lib/receipts";
import type { GoodsReceipt } from "@/lib/types";

/** How far along the scanning is, across every serialized line on the receipt. */
function scanned(receipt: GoodsReceipt): { done: number; expected: number } {
  return receipt.lines.filter(isSerial).reduce(
    (running, line) => ({
      done: running.done + line.scannedCount,
      expected: running.expected + line.quantity,
    }),
    { done: 0, expected: 0 },
  );
}

export function ReceiptsList() {
  const t = useTranslations("receipts");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const can = useCan();

  const suppliers = useSupplierLookup();
  const customers = useCustomerLookup();
  const locations = useLocationLookup();

  const initialStatus = useSearchParams().get("status");

  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [status, setStatus] = useState<string | null>(initialStatus);
  const [source, setSource] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<GoodsReceipt>("receipts", {
    page,
    search: debouncedSearch || undefined,
    status: status ?? undefined,
    acquisitionSource: source ?? undefined,
  });

  const receipts = query.data?.items ?? [];

  return (
    <ListShell
      title={t("title")}
      subtitle={t("subtitle")}
      action={
        can(Permission.Receiving.Manage) && (
          <Button
            component={Link}
            href="/receipts/new"
            leftSection={<IconPlus size={16} />}
          >
            {t("new")}
          </Button>
        )
      }
      search={{
        value: search,
        onChange: reset(setSearch),
        placeholder: t("searchPlaceholder"),
      }}
      filters={
        <>
          <Select
            value={status}
            onChange={reset(setStatus)}
            placeholder={t("filterStatus")}
            clearable
            w={{ base: "100%", sm: 180 }}
            data={["draft", "confirmed", "cancelled"].map((value) => ({
              value,
              label: tDoc(`status.${value}`),
            }))}
          />
          <Select
            value={source}
            onChange={reset(setSource)}
            placeholder={t("filterSource")}
            clearable
            w={{ base: "100%", sm: 180 }}
            data={["supplier", "trade_in"].map((value) => ({
              value,
              label: tDoc(`source.${value}`),
            }))}
          />
        </>
      }
      head={
        <Table.Tr>
          <Table.Th>{tDoc("number")}</Table.Th>
          <Table.Th>{t("source")}</Table.Th>
          <Table.Th>{t("location")}</Table.Th>
          <Table.Th>{tCommon("status")}</Table.Th>
          <Table.Th>{t("scannedUnits")}</Table.Th>
          <Table.Th>{tDoc("subtotals")}</Table.Th>
        </Table.Tr>
      }
      isLoading={query.isLoading}
      error={query.error}
      isEmpty={receipts.length === 0}
      total={query.data?.totalItems ?? 0}
      page={page}
      pagesCount={query.data?.pagesCount ?? 0}
      onPageChange={setPage}
    >
      {receipts.map((receipt) => {
        const progress = scanned(receipt);
        // A trade-in names no supplier; it may name the walk-in it came from.
        const from =
          receipt.acquisitionSource === "supplier"
            ? suppliers.get(receipt.supplierId)
            : customers.get(receipt.customerId);

        return (
          <Table.Tr key={receipt.id}>
            <Table.Td>
              <Anchor component={Link} href={`/receipts/${receipt.id}`} fw={500}>
                {receipt.number}
              </Anchor>
            </Table.Td>
            <Table.Td>
              <Badge
                size="sm"
                variant="light"
                color={receipt.acquisitionSource === "supplier" ? "blue" : "grape"}
              >
                {tDoc(`source.${receipt.acquisitionSource}`)}
              </Badge>
              <Text size="xs" c="dimmed">
                {from ?? tCommon("none")}
              </Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm">
                {locations.get(receipt.locationId) ?? tCommon("none")}
              </Text>
            </Table.Td>
            <Table.Td>
              <DocumentStatusBadge status={receipt.status} />
            </Table.Td>
            <Table.Td>
              <Text size="sm">
                {progress.expected === 0
                  ? tCommon("none")
                  : t("progress", {
                      scanned: progress.done,
                      expected: progress.expected,
                    })}
              </Text>
            </Table.Td>
            <Table.Td>
              <Subtotals subtotals={receipt.subtotals} />
            </Table.Td>
          </Table.Tr>
        );
      })}
    </ListShell>
  );
}
