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
import { useCustomerLookup, useLocationLookup } from "@/hooks/use-lookup";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { CUSTOMER_RETURN_REASON_COLOR } from "@/lib/customer-returns";
import { Permission } from "@/lib/permissions";
import { CUSTOMER_RETURN_REASONS, type CustomerReturn } from "@/lib/types";

export function CustomerReturnsList() {
  const t = useTranslations("customerReturns");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { formatDate } = useDateFormat();
  const can = useCan();

  const customers = useCustomerLookup();
  const locations = useLocationLookup();

  const initialStatus = useSearchParams().get("status");

  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [status, setStatus] = useState<string | null>(initialStatus);
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [reason, setReason] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<CustomerReturn>("customer-returns", {
    page,
    search: debouncedSearch || undefined,
    status: status ?? undefined,
    customerId: customerId ?? undefined,
    reason: reason ?? undefined,
  });

  const returns = query.data?.items ?? [];

  return (
    <ListShell
      title={t("title")}
      subtitle={t("subtitle")}
      action={
        can(Permission.CustomerReturn.Manage) && (
          <Button
            component={Link}
            href="/customer-returns/new"
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
            value={customerId}
            onChange={reset(setCustomerId)}
            placeholder={t("filterCustomer")}
            clearable
            searchable
            w={{ base: "100%", sm: 200 }}
            data={customers.all.map((customer) => ({
              value: customer.id,
              label: customer.fullName,
            }))}
          />
          <Select
            value={reason}
            onChange={reset(setReason)}
            placeholder={t("filterReason")}
            clearable
            w={{ base: "100%", sm: 180 }}
            data={CUSTOMER_RETURN_REASONS.map((value) => ({
              value,
              label: t(`reason.${value}`),
            }))}
          />
        </>
      }
      head={
        <Table.Tr>
          <Table.Th>{tDoc("number")}</Table.Th>
          <Table.Th>{t("customer")}</Table.Th>
          <Table.Th>{t("location")}</Table.Th>
          <Table.Th>{tDoc("reason")}</Table.Th>
          <Table.Th>{tCommon("status")}</Table.Th>
          <Table.Th>{t("refunded")}</Table.Th>
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
      {returns.map((document) => (
        <Table.Tr key={document.id}>
          <Table.Td>
            <Anchor
              component={Link}
              href={`/customer-returns/${document.id}`}
              fw={500}
            >
              {document.number}
            </Anchor>
          </Table.Td>
          <Table.Td>
            <Text size="sm">
              {document.customerId === null
                ? t("walkIn")
                : (customers.get(document.customerId) ?? tCommon("none"))}
            </Text>
          </Table.Td>
          <Table.Td>
            <Text size="sm">
              {locations.get(document.locationId) ?? tCommon("none")}
            </Text>
          </Table.Td>
          <Table.Td>
            <Badge
              size="sm"
              variant="light"
              color={CUSTOMER_RETURN_REASON_COLOR[document.reason]}
            >
              {t(`reason.${document.reason}`)}
            </Badge>
          </Table.Td>
          <Table.Td>
            <DocumentStatusBadge status={document.status} />
          </Table.Td>
          <Table.Td>
            <Subtotals subtotals={document.subtotals} />
          </Table.Td>
          <Table.Td>
            <Text size="sm" c="dimmed">
              {formatDate(document.createdAt)}
            </Text>
          </Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}
