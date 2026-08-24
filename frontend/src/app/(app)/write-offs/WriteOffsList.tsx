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
import { useDateFormat } from "@/hooks/use-date-format";
import { useLocationLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { Permission } from "@/lib/permissions";
import { WRITE_OFF_REASON_COLOR } from "@/lib/removals";
import { WRITE_OFF_REASONS, type WriteOff } from "@/lib/types";

export function WriteOffsList() {
  const t = useTranslations("writeOffs");
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
  const [reason, setReason] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<WriteOff>("write-offs", {
    page,
    search: debouncedSearch || undefined,
    status: status ?? undefined,
    locationId: locationId ?? undefined,
    reason: reason ?? undefined,
  });

  const writeOffs = query.data?.items ?? [];

  return (
    <ListShell
      title={t("title")}
      subtitle={t("subtitle")}
      action={
        can(Permission.WriteOff.Manage) && (
          <Button
            component={Link}
            href="/write-offs/new"
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
          <Select
            value={reason}
            onChange={reset(setReason)}
            placeholder={t("filterReason")}
            clearable
            w={{ base: "100%", sm: 180 }}
            data={WRITE_OFF_REASONS.map((value) => ({
              value,
              label: tDoc(`writeOffReason.${value}`),
            }))}
          />
        </>
      }
      head={
        <Table.Tr>
          <Table.Th>{tDoc("number")}</Table.Th>
          <Table.Th>{t("location")}</Table.Th>
          <Table.Th>{tDoc("reason")}</Table.Th>
          <Table.Th>{tCommon("status")}</Table.Th>
          <Table.Th>{t("lines")}</Table.Th>
          <Table.Th>{tDoc("created")}</Table.Th>
        </Table.Tr>
      }
      isLoading={query.isLoading}
      error={query.error}
      isEmpty={writeOffs.length === 0}
      total={query.data?.totalItems ?? 0}
      page={page}
      pagesCount={query.data?.pagesCount ?? 0}
      onPageChange={setPage}
    >
      {writeOffs.map((writeOff) => (
        <Table.Tr key={writeOff.id}>
          <Table.Td>
            <Anchor component={Link} href={`/write-offs/${writeOff.id}`} fw={500}>
              {writeOff.number}
            </Anchor>
          </Table.Td>
          <Table.Td>
            <Text size="sm">
              {locations.get(writeOff.locationId) ?? tCommon("none")}
            </Text>
          </Table.Td>
          <Table.Td>
            <Badge
              size="sm"
              variant="light"
              color={WRITE_OFF_REASON_COLOR[writeOff.reason]}
            >
              {tDoc(`writeOffReason.${writeOff.reason}`)}
            </Badge>
          </Table.Td>
          <Table.Td>
            <DocumentStatusBadge status={writeOff.status} />
          </Table.Td>
          <Table.Td>
            <Text size="sm">{writeOff.lineCount}</Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm" c="dimmed">
              {formatDate(writeOff.createdAt)}
            </Text>
          </Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}
