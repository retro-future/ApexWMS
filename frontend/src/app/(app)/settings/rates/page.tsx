"use client";

import { SegmentedControl, Table } from "@mantine/core";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { ListShell } from "@/components/ListShell";
import { useCan } from "@/components/MeProvider";
import { useDateFormat } from "@/hooks/use-date-format";
import { useResourceList } from "@/hooks/use-resource";
import { Permission } from "@/lib/permissions";
import { RATE_KINDS, type ExchangeRate, type RateKind } from "@/lib/types";

const PAGE_SIZE = 25;

/**
 * Every rate the store has quoted, read-only.
 *
 * Re-quoting a day appends rather than replaces, so the same date can
 * appear twice and the newer row is the one that was in force. Showing both
 * is the point: a rate corrected mid-morning is exactly what someone comes
 * here to find.
 */
export default function RateHistoryPage() {
  const t = useTranslations("rates");
  const can = useCan();
  const { formatDateTime } = useDateFormat();
  const [kind, setKind] = useState<RateKind>("sale");
  const [page, setPage] = useState(1);

  const list = useResourceList<ExchangeRate>(
    "exchange-rates",
    { page, pageSize: PAGE_SIZE, kind },
    { enabled: can(Permission.ExchangeRate.View) },
  );

  return (
    <ListShell
      title={t("historyTitle")}
      subtitle={t("historyHint")}
      filters={
        <SegmentedControl
          value={kind}
          onChange={(value) => {
            setKind(value as RateKind);
            setPage(1);
          }}
          data={RATE_KINDS.map((value) => ({ value, label: t(`kind.${value}`) }))}
        />
      }
      head={
        <Table.Tr>
          <Table.Th>{t("effectiveOn")}</Table.Th>
          <Table.Th>{t("rate")}</Table.Th>
          <Table.Th>{t("setAt")}</Table.Th>
        </Table.Tr>
      }
      isLoading={list.isPending}
      error={list.error}
      isEmpty={list.data?.items.length === 0}
      emptyMessage={t("neverSet")}
      total={list.data?.totalItems ?? 0}
      page={page}
      pagesCount={list.data?.pagesCount ?? 1}
      onPageChange={setPage}
    >
      {list.data?.items.map((rate) => (
        <Table.Tr key={rate.id}>
          <Table.Td>{rate.effectiveOn}</Table.Td>
          <Table.Td>{rate.somPerUsd}</Table.Td>
          <Table.Td>{formatDateTime(rate.setAt)}</Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}
