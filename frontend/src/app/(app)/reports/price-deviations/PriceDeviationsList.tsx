"use client";

import { Anchor, Group, Select, Table, Text, TextInput, UnstyledButton } from "@mantine/core";
import { IconArrowsSort } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { ListShell } from "@/components/ListShell";
import { useDateFormat } from "@/hooks/use-date-format";
import { useCustomerLookup, useEmployeeLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { formatMoney } from "@/lib/money";
import type { PriceDeviation } from "@/lib/types";

/**
 * FR-9.7. Every confirmed line charged something other than the price the
 * system resolved at confirm, in **both** directions — a handset sold above
 * its asking price is information too.
 *
 * Sorting is the server's (`sort=approver|customer`), because the pattern
 * the report exists to show — the same manager and the same customer, over
 * and over — is spread across pages, and sorting one page would only
 * rearrange what happens to be on it.
 */

type SortKey = "confirmed_at" | "approver" | "customer";

export function PriceDeviationsList() {
  const t = useTranslations("reports");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { formatDate } = useDateFormat();

  const customers = useCustomerLookup();
  const employees = useEmployeeLookup();

  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [approvedBy, setApprovedBy] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>("confirmed_at");
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<PriceDeviation>("reports/price-deviations", {
    page,
    sort,
    fromDate: from ? new Date(from).toISOString() : undefined,
    // Through the end of the chosen day, not its first instant.
    toDate: to ? new Date(`${to}T23:59:59.999Z`).toISOString() : undefined,
    approvedBy: approvedBy ?? undefined,
    customerId: customerId ?? undefined,
  });

  const rows = query.data?.items ?? [];

  function toggleSort(key: SortKey) {
    reset(setSort)(sort === key ? "confirmed_at" : key);
  }

  return (
    <ListShell
      title={t("priceDeviationsTitle")}
      subtitle={t("priceDeviationsSubtitle")}
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
            value={approvedBy}
            onChange={reset(setApprovedBy)}
            placeholder={t("filterApprover")}
            clearable
            searchable
            w={{ base: "100%", sm: 200 }}
            data={(employees.all ?? []).map((employee) => ({
              value: employee.id,
              label: employee.fullName,
            }))}
          />
          <Select
            value={customerId}
            onChange={reset(setCustomerId)}
            placeholder={t("filterCustomer")}
            clearable
            searchable
            w={{ base: "100%", sm: 200 }}
            data={(customers.all ?? []).map((customer) => ({
              value: customer.id,
              label: customer.fullName,
            }))}
          />
        </>
      }
      head={
        <Table.Tr>
          <Table.Th>{t("date")}</Table.Th>
          <Table.Th>{t("invoice")}</Table.Th>
          <Table.Th>{t("handset")}</Table.Th>
          <Table.Th>{tDoc("resolvedPrice")}</Table.Th>
          <Table.Th>{tDoc("chargedPrice")}</Table.Th>
          <Table.Th>{t("difference")}</Table.Th>
          <Table.Th>
            <SortHeader
              label={t("approver")}
              active={sort === "approver"}
              onToggle={() => toggleSort("approver")}
            />
          </Table.Th>
          <Table.Th>
            <SortHeader
              label={t("filterCustomer")}
              active={sort === "customer"}
              onToggle={() => toggleSort("customer")}
            />
          </Table.Th>
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
        <Table.Tr key={`${row.invoiceId}-${row.imei ?? row.productId}`}>
          <Table.Td>
            <Text size="sm">{formatDate(row.confirmedAt)}</Text>
          </Table.Td>
          <Table.Td>
            <Anchor component={Link} href={`/invoices/${row.invoiceId}`} fw={500}>
              {row.invoiceNumber}
            </Anchor>
          </Table.Td>
          <Table.Td>
            <Text size="sm">{row.productName}</Text>
            {row.imei && (
              <Text size="xs" c="dimmed" ff="monospace">
                {row.imei}
              </Text>
            )}
          </Table.Td>
          <Table.Td>
            <Text size="sm" c="dimmed">
              {formatMoney(row.resolvedPrice)}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm" fw={600}>
              {formatMoney(row.chargedPrice)}
            </Text>
          </Table.Td>
          <Table.Td>
            {/* Both directions: a discount is red, a sale above the asking
                price is teal, and neither is hidden. */}
            <Text size="sm" c={row.difference.minor < 0 ? "red" : "teal"}>
              {row.difference.minor > 0 ? "+" : ""}
              {formatMoney(row.difference)}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">{row.priceApprovedByName ?? t("unattributed")}</Text>
            {row.priceNote && (
              <Text size="xs" c="dimmed">
                {row.priceNote}
              </Text>
            )}
          </Table.Td>
          <Table.Td>
            <Text size="sm">{row.customerName ?? tCommon("none")}</Text>
          </Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}

/** A column header that switches the server-side sort on and off. */
function SortHeader({
  label,
  active,
  onToggle,
}: {
  label: string;
  active: boolean;
  onToggle: () => void;
}) {
  return (
    <UnstyledButton onClick={onToggle}>
      <Group gap="3xs" wrap="nowrap">
        <Text size="sm" fw={active ? 700 : 600}>
          {label}
        </Text>
        <IconArrowsSort size={14} stroke={1.5} />
      </Group>
    </UnstyledButton>
  );
}
