"use client";

import { Anchor, Table, Text } from "@mantine/core";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { ListShell } from "@/components/ListShell";
import { useDateFormat } from "@/hooks/use-date-format";
import { useResourceList } from "@/hooks/use-resource";
import { formatMoney } from "@/lib/money";
import type { Debtor } from "@/lib/types";

/**
 * FR-11.10: who owes the store money, and nothing more.
 *
 * No ageing buckets and no overdue column, because store credit has no due
 * date by design (PRD §4.7) — there is nothing to be late against. What the
 * list is ordered by instead is the age of each customer's oldest open
 * invoice, which is what makes a debt that has been sitting for a year rise
 * to the top on its own. The server does that ordering, so this table shows
 * the rows in the order they arrive.
 */
export function DebtorsList() {
  const t = useTranslations("reports");
  const tCredit = useTranslations("credit");
  const tCommon = useTranslations("common");
  const { formatDate } = useDateFormat();

  const [page, setPage] = useState(1);
  const query = useResourceList<Debtor>("reports/debtors", { page });

  const rows = query.data?.items ?? [];

  return (
    <ListShell
      title={t("debtorsTitle")}
      subtitle={t("debtorsSubtitle")}
      head={
        <Table.Tr>
          <Table.Th>{t("filterCustomer")}</Table.Th>
          <Table.Th>{tCredit("phone")}</Table.Th>
          <Table.Th>{tCredit("balance")}</Table.Th>
          <Table.Th>{t("oldestDebt")}</Table.Th>
          <Table.Th>{t("openInvoices")}</Table.Th>
        </Table.Tr>
      }
      isLoading={query.isLoading}
      error={query.error}
      isEmpty={rows.length === 0}
      emptyMessage={t("noDebtors")}
      total={query.data?.totalItems ?? 0}
      page={page}
      pagesCount={query.data?.pagesCount ?? 0}
      onPageChange={setPage}
    >
      {rows.map((row) => (
        <Table.Tr key={row.customerId}>
          <Table.Td>
            <Anchor component={Link} href={`/customers/${row.customerId}`} fw={500}>
              {row.fullName}
            </Anchor>
          </Table.Td>
          <Table.Td>
            <Text size="sm" c={row.phone ? undefined : "dimmed"}>
              {row.phone ?? tCommon("none")}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm" fw={600}>
              {formatMoney(row.balance)}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">{tCredit("days", { count: row.daysSinceOldest })}</Text>
            <Text size="xs" c="dimmed">
              {formatDate(row.oldestOpenAt)}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">{row.openInvoiceCount}</Text>
          </Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}
