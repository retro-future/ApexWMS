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
import { useDateFormat } from "@/hooks/use-date-format";
import { useSupplierLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { Permission } from "@/lib/permissions";
import type { Fulfilment, PurchaseOrder } from "@/lib/types";

/** FR-3.9: how much of what was ordered has actually turned up. */
const FULFILMENT_COLOR: Record<Fulfilment, string> = {
  pending: "gray",
  partial: "yellow",
  complete: "teal",
};

export function PurchaseOrdersList() {
  const t = useTranslations("purchaseOrders");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { formatDate } = useDateFormat();
  const can = useCan();
  const suppliers = useSupplierLookup();

  // The dashboard links here with a status already chosen.
  const initialStatus = useSearchParams().get("status");

  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [status, setStatus] = useState<string | null>(initialStatus);
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<PurchaseOrder>("purchase-orders", {
    page,
    search: debouncedSearch || undefined,
    status: status ?? undefined,
  });

  const orders = query.data?.items ?? [];

  return (
    <ListShell
      title={t("title")}
      subtitle={t("subtitle")}
      action={
        can(Permission.PurchaseOrder.Manage) && (
          <Button
            component={Link}
            href="/purchase-orders/new"
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
          <Table.Th>{t("supplier")}</Table.Th>
          <Table.Th>{tCommon("status")}</Table.Th>
          <Table.Th>{t("received")}</Table.Th>
          <Table.Th>{tDoc("subtotals")}</Table.Th>
          <Table.Th>{tDoc("created")}</Table.Th>
        </Table.Tr>
      }
      isLoading={query.isLoading}
      error={query.error}
      isEmpty={orders.length === 0}
      total={query.data?.totalItems ?? 0}
      page={page}
      pagesCount={query.data?.pagesCount ?? 0}
      onPageChange={setPage}
    >
      {orders.map((order) => (
        <Table.Tr key={order.id}>
          <Table.Td>
            <Anchor component={Link} href={`/purchase-orders/${order.id}`} fw={500}>
              {order.number}
            </Anchor>
          </Table.Td>
          <Table.Td>
            <Text size="sm">
              {suppliers.get(order.supplierId) ?? tCommon("none")}
            </Text>
          </Table.Td>
          <Table.Td>
            <DocumentStatusBadge status={order.status} />
          </Table.Td>
          <Table.Td>
            <Badge
              size="sm"
              variant="light"
              color={FULFILMENT_COLOR[order.fulfilment]}
            >
              {tDoc(`fulfilment.${order.fulfilment}`)}
            </Badge>
          </Table.Td>
          <Table.Td>
            <Subtotals subtotals={order.subtotals} />
          </Table.Td>
          <Table.Td>
            <Text size="sm" c="dimmed">
              {formatDate(order.createdAt)}
            </Text>
          </Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}
