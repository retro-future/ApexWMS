"use client";

import { Anchor, Select, Table, Text, TextInput } from "@mantine/core";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { DocumentLink } from "@/app/(app)/reports/DocumentLink";
import { ListShell } from "@/components/ListShell";
import { useDateFormat } from "@/hooks/use-date-format";
import { useLocationLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { formatMoney } from "@/lib/money";
import type { DocumentType, FinancialLedgerRow, TransactionType } from "@/lib/types";

const TXN_TYPES: TransactionType[] = [
  "purchase",
  "sale_revenue",
  "cogs",
  "write_off_loss",
  "supplier_return_credit",
  "sales_return_refund",
  "count_adjustment",
  "payment_received",
];

const DOCUMENT_TYPES: DocumentType[] = [
  "goods_receipt",
  "sales_invoice",
  "supplier_return",
  "stock_count",
  "write_off",
  "payment",
];

/**
 * FR-10.3: the raw money ledger, mirroring the movement log.
 *
 * Each row carries its own currency and the table shows no total. This is
 * the one place a som payment and a dollar sale sit next to each other
 * (§4.6), so a column footer here would be adding the two together.
 */
export function FinancialLedgerList() {
  const t = useTranslations("reports");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { formatDateTime } = useDateFormat();

  const locations = useLocationLookup();

  // The month-end figures link here with the filter in the URL. Read it once,
  // on mount — after that the selects own the state, same as every list page.
  const params = useSearchParams();
  const [from, setFrom] = useState(params.get("from") ?? "");
  const [to, setTo] = useState(params.get("to") ?? "");
  const [txnType, setTxnType] = useState<string | null>(params.get("txnType"));
  const [documentType, setDocumentType] = useState<string | null>(
    params.get("documentType"),
  );
  const [locationId, setLocationId] = useState<string | null>(
    params.get("locationId"),
  );
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<FinancialLedgerRow>("reports/financial-ledger", {
    page,
    fromDate: from ? new Date(from).toISOString() : undefined,
    // Through the end of the chosen day, not its first instant.
    toDate: to ? new Date(`${to}T23:59:59.999Z`).toISOString() : undefined,
    txnType: txnType ?? undefined,
    documentType: documentType ?? undefined,
    locationId: locationId ?? undefined,
  });

  const rows = query.data?.items ?? [];

  return (
    <ListShell
      title={t("financialLedgerTitle")}
      subtitle={t("financialLedgerSubtitle")}
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
            value={txnType}
            onChange={reset(setTxnType)}
            placeholder={t("filterTxnType")}
            clearable
            w={{ base: "100%", sm: 220 }}
            data={TXN_TYPES.map((type) => ({
              value: type,
              label: t(`txnType.${type}`),
            }))}
          />
          <Select
            value={documentType}
            onChange={reset(setDocumentType)}
            placeholder={t("filterDocumentType")}
            clearable
            w={{ base: "100%", sm: 200 }}
            data={DOCUMENT_TYPES.map((type) => ({
              value: type,
              label: t(`documentType.${type}`),
            }))}
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
        </>
      }
      head={
        <Table.Tr>
          <Table.Th>{t("date")}</Table.Th>
          <Table.Th>{t("entry")}</Table.Th>
          <Table.Th>{t("amount")}</Table.Th>
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
            <Text size="sm">{t(`txnType.${row.txnType}`)}</Text>
            {row.note && (
              <Text size="xs" c="dimmed">
                {row.note}
              </Text>
            )}
          </Table.Td>
          <Table.Td>
            {/* Signed per §4.6: negative is money out, and it stays negative. */}
            <Text size="sm" fw={600} c={row.amountMinor < 0 ? "red" : "teal"}>
              {formatMoney(row.amountMinor, row.currency)}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">{row.productName ?? tCommon("none")}</Text>
            {row.imei && row.deviceUnitId && (
              <Anchor
                component={Link}
                href={`/device-units/${row.deviceUnitId}`}
                size="xs"
                ff="monospace"
              >
                {row.imei}
              </Anchor>
            )}
          </Table.Td>
          <Table.Td>
            <Text size="sm">{row.locationName ?? tCommon("none")}</Text>
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
