"use client";

import { Anchor, Badge, Button, Group, Select, Table, Text } from "@mantine/core";
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
import { useCustomerLookup, useLocationLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { formatMoney } from "@/lib/money";
import { Permission } from "@/lib/permissions";
import type { SalesInvoice } from "@/lib/types";

export function InvoicesList() {
  const t = useTranslations("invoices");
  const tCredit = useTranslations("credit");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const can = useCan();

  const customers = useCustomerLookup();
  const locations = useLocationLookup();

  const initialStatus = useSearchParams().get("status");

  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [status, setStatus] = useState<string | null>(initialStatus);
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<SalesInvoice>("invoices", {
    page,
    search: debouncedSearch || undefined,
    status: status ?? undefined,
  });

  const invoices = query.data?.items ?? [];

  return (
    <ListShell
      title={t("title")}
      subtitle={t("subtitle")}
      action={
        can(Permission.Sales.Manage) && (
          <Button
            component={Link}
            href="/invoices/new"
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
      }
      head={
        <Table.Tr>
          <Table.Th>{tDoc("number")}</Table.Th>
          <Table.Th>{t("customer")}</Table.Th>
          <Table.Th>{t("location")}</Table.Th>
          <Table.Th>{tCommon("status")}</Table.Th>
          <Table.Th>{t("lineCount")}</Table.Th>
          <Table.Th>{tDoc("subtotals")}</Table.Th>
          <Table.Th>{tCredit("remaining")}</Table.Th>
        </Table.Tr>
      }
      isLoading={query.isLoading}
      error={query.error}
      isEmpty={invoices.length === 0}
      total={query.data?.totalItems ?? 0}
      page={page}
      pagesCount={query.data?.pagesCount ?? 0}
      onPageChange={setPage}
    >
      {invoices.map((invoice) => (
        <Table.Tr key={invoice.id}>
          <Table.Td>
            <Group gap="2xs" wrap="nowrap">
              <Anchor component={Link} href={`/invoices/${invoice.id}`} fw={500}>
                {invoice.number}
              </Anchor>
              {invoice.paymentType !== "paid_in_full" && (
                <Badge size="xs" variant="light" color="grape">
                  {tCredit(
                    invoice.paymentType === "store_credit"
                      ? "storeCredit"
                      : "creditCompany",
                  )}
                </Badge>
              )}
            </Group>
          </Table.Td>
          <Table.Td>
            {/* A walk-in names nobody, and that is not missing data. */}
            <Text size="sm">
              {customers.get(invoice.customerId) ?? t("walkIn")}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">
              {locations.get(invoice.locationId) ?? tCommon("none")}
            </Text>
          </Table.Td>
          <Table.Td>
            <DocumentStatusBadge status={invoice.status} />
          </Table.Td>
          <Table.Td>
            <Text size="sm">{invoice.lines.length}</Text>
          </Table.Td>
          <Table.Td>
            {/* Empty on a draft: a draft holds no prices (FR-4.5b1). */}
            <Subtotals subtotals={invoice.subtotals} />
          </Table.Td>
          <Table.Td>
            {/* Only store credit can owe anything: a financed sale was paid
                in full by the company at confirm (FR-11.4). */}
            {invoice.paymentType === "store_credit" ? (
              <Text size="sm" fw={invoice.remainingMinor > 0 ? 600 : undefined}>
                {formatMoney(invoice.remainingMinor, "UZS")}
              </Text>
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
