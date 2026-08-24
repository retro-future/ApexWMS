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
import { useLocationLookup, useSupplierLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { Permission } from "@/lib/permissions";
import { SUPPLIER_RETURN_REASON_COLOR } from "@/lib/removals";
import { SUPPLIER_RETURN_REASONS, type SupplierReturn } from "@/lib/types";

export function SupplierReturnsList() {
  const t = useTranslations("supplierReturns");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { formatDate } = useDateFormat();
  const can = useCan();

  const suppliers = useSupplierLookup();
  const locations = useLocationLookup();

  const initialStatus = useSearchParams().get("status");

  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [status, setStatus] = useState<string | null>(initialStatus);
  const [supplierId, setSupplierId] = useState<string | null>(null);
  const [reason, setReason] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<SupplierReturn>("supplier-returns", {
    page,
    search: debouncedSearch || undefined,
    status: status ?? undefined,
    supplierId: supplierId ?? undefined,
    reason: reason ?? undefined,
  });

  const returns = query.data?.items ?? [];

  return (
    <ListShell
      title={t("title")}
      subtitle={t("subtitle")}
      action={
        can(Permission.SupplierReturn.Manage) && (
          <Button
            component={Link}
            href="/supplier-returns/new"
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
            value={supplierId}
            onChange={reset(setSupplierId)}
            placeholder={t("filterSupplier")}
            clearable
            searchable
            w={{ base: "100%", sm: 200 }}
            data={suppliers.all.map((supplier) => ({
              value: supplier.id,
              label: supplier.name,
            }))}
          />
          <Select
            value={reason}
            onChange={reset(setReason)}
            placeholder={t("filterReason")}
            clearable
            w={{ base: "100%", sm: 180 }}
            data={SUPPLIER_RETURN_REASONS.map((value) => ({
              value,
              label: tDoc(`returnReason.${value}`),
            }))}
          />
        </>
      }
      head={
        <Table.Tr>
          <Table.Th>{tDoc("number")}</Table.Th>
          <Table.Th>{t("supplier")}</Table.Th>
          <Table.Th>{t("location")}</Table.Th>
          <Table.Th>{tDoc("reason")}</Table.Th>
          <Table.Th>{tCommon("status")}</Table.Th>
          <Table.Th>{t("lines")}</Table.Th>
          <Table.Th>{tDoc("created")}</Table.Th>
        </Table.Tr>
      }
      isLoading={query.isLoading}
      error={query.error}
      isEmpty={returns.length === 0}
      total={query.data?.totalItems ?? 0}
      page={page}
      pagesCount={query.data?.pagesCount ?? 0}
      onPageChange={setPage}
    >
      {returns.map((supplierReturn) => (
        <Table.Tr key={supplierReturn.id}>
          <Table.Td>
            <Anchor
              component={Link}
              href={`/supplier-returns/${supplierReturn.id}`}
              fw={500}
            >
              {supplierReturn.number}
            </Anchor>
          </Table.Td>
          <Table.Td>
            <Text size="sm">
              {suppliers.get(supplierReturn.supplierId) ?? tCommon("none")}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">
              {locations.get(supplierReturn.locationId) ?? tCommon("none")}
            </Text>
          </Table.Td>
          <Table.Td>
            <Badge
              size="sm"
              variant="light"
              color={SUPPLIER_RETURN_REASON_COLOR[supplierReturn.reason]}
            >
              {tDoc(`returnReason.${supplierReturn.reason}`)}
            </Badge>
          </Table.Td>
          <Table.Td>
            <DocumentStatusBadge status={supplierReturn.status} />
          </Table.Td>
          <Table.Td>
            <Text size="sm">{supplierReturn.lineCount}</Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm" c="dimmed">
              {formatDate(supplierReturn.createdAt)}
            </Text>
          </Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}
