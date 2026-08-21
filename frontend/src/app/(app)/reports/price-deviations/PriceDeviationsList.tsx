"use client";

import { Anchor, Group, Select, Table, Text, TextInput, UnstyledButton } from "@mantine/core";
import { IconArrowsSort } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { ListShell } from "@/components/ListShell";
import { useCustomerLookup, useEmployeeLookup } from "@/hooks/use-lookup";
import { useResourceList } from "@/hooks/use-resource";
import { formatMoney } from "@/lib/money";
import type { PriceDeviation } from "@/lib/types";

/**
 * FR-9.7. Every confirmed line charged something other than the price the
 * system resolved at confirm, in **both** directions — a handset sold above
 * its asking price is information too.
 *
 * Sorting by approver and by customer is done here rather than on the
 * server: the list query carries no `orderBy` (that lands with M8), and
 * what the report is looking for — the same manager and the same customer,
 * over and over — is visible within a page.
 */

type SortKey = "approver" | "customer" | null;

export function PriceDeviationsList() {
  const t = useTranslations("reports");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");

  const customers = useCustomerLookup();
  const employees = useEmployeeLookup();

  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [approvedBy, setApprovedBy] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>(null);
  const [page, setPage] = useState(1);

  function reset<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value);
      setPage(1);
    };
  }

  const query = useResourceList<PriceDeviation>("reports/price-deviations", {
    page,
    fromDate: from ? new Date(from).toISOString() : undefined,
    // Through the end of the chosen day, not its first instant.
    toDate: to ? new Date(`${to}T23:59:59.999Z`).toISOString() : undefined,
    approvedBy: approvedBy ?? undefined,
    customerId: customerId ?? undefined,
  });

  const label = (row: PriceDeviation) =>
    sort === "approver"
      ? (employees.get(row.priceApprovedBy) ?? "")
      : (customers.get(row.customerId) ?? "");

  const rows = [...(query.data?.items ?? [])];
  if (sort) rows.sort((a, b) => label(a).localeCompare(label(b)));

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
              onToggle={() => setSort(sort === "approver" ? null : "approver")}
            />
          </Table.Th>
          <Table.Th>
            <SortHeader
              label={t("filterCustomer")}
              active={sort === "customer"}
              onToggle={() => setSort(sort === "customer" ? null : "customer")}
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
            <Text size="sm">{new Date(row.confirmedAt).toLocaleDateString()}</Text>
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
              {formatMoney(row.resolvedPriceMinor, row.currency)}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm" fw={600}>
              {formatMoney(row.chargedPriceMinor, row.currency)}
            </Text>
          </Table.Td>
          <Table.Td>
            {/* Both directions: a discount is red, a sale above the asking
                price is teal, and neither is hidden. */}
            <Text size="sm" c={row.differenceMinor < 0 ? "red" : "teal"}>
              {row.differenceMinor > 0 ? "+" : ""}
              {formatMoney(row.differenceMinor, row.currency)}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">
              {employees.get(row.priceApprovedBy) ?? t("unattributed")}
            </Text>
            {row.priceNote && (
              <Text size="xs" c="dimmed">
                {row.priceNote}
              </Text>
            )}
          </Table.Td>
          <Table.Td>
            <Text size="sm">{customers.get(row.customerId) ?? tCommon("none")}</Text>
          </Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}

/** A column header that toggles the client-side sort on and off. */
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
