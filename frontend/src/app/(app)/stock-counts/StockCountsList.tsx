"use client";

import { Anchor, Button, Group, Select, Table, Text } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconPlus } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { CountStepBadge } from "@/app/(app)/stock-counts/CountStepBadge";
import { ListShell } from "@/components/ListShell";
import { useCan } from "@/components/MeProvider";
import { useDateFormat } from "@/hooks/use-date-format";
import { useLocationLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { Permission } from "@/lib/permissions";
import type { StockCount } from "@/lib/types";

export function StockCountsList() {
  const t = useTranslations("stockCounts");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { formatDate } = useDateFormat();
  const can = useCan();

  const locations = useLocationLookup();

  const initialStatus = useSearchParams().get("status");

  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [status, setStatus] = useState<string | null>(initialStatus);
  const [locationId, setLocationId] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<StockCount>("stock-counts", {
    page,
    search: debouncedSearch || undefined,
    status: status ?? undefined,
    locationId: locationId ?? undefined,
  });

  const counts = query.data?.items ?? [];

  return (
    <ListShell
      title={t("title")}
      subtitle={t("subtitle")}
      action={
        can(Permission.StockCount.Run) && (
          <Button
            component={Link}
            href="/stock-counts/new"
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
          <Table.Th>{tDoc("number")}</Table.Th>
          <Table.Th>{t("location")}</Table.Th>
          <Table.Th>{tCommon("status")}</Table.Th>
          <Table.Th>{t("findings")}</Table.Th>
          <Table.Th>{tDoc("created")}</Table.Th>
        </Table.Tr>
      }
      isLoading={query.isLoading}
      error={query.error}
      isEmpty={counts.length === 0}
      total={query.data?.totalItems ?? 0}
      page={page}
      pagesCount={query.data?.pagesCount ?? 0}
      onPageChange={setPage}
    >
      {counts.map((count) => (
        <Table.Tr key={count.id}>
          <Table.Td>
            <Anchor component={Link} href={`/stock-counts/${count.id}`} fw={500}>
              {count.number}
            </Anchor>
          </Table.Td>
          <Table.Td>
            <Text size="sm">
              {locations.get(count.locationId) ?? tCommon("none")}
            </Text>
          </Table.Td>
          <Table.Td>
            <CountStepBadge count={count} />
          </Table.Td>
          <Table.Td>
            <Group gap="xs" wrap="nowrap">
              <Text size="sm" c="teal">
                {count.matchedCount}
              </Text>
              <Text size="sm" c="orange">
                {count.missingCount}
              </Text>
              <Text size="sm" c="grape">
                {count.unexpectedCount}
              </Text>
            </Group>
          </Table.Td>
          <Table.Td>
            <Text size="sm" c="dimmed">
              {formatDate(count.createdAt)}
            </Text>
          </Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}
