"use client";

import { Badge, Button, Group, Stack, Table, Text } from "@mantine/core";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { useCan } from "@/components/MeProvider";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useDateFormat } from "@/hooks/use-date-format";
import { useDocumentAction } from "@/hooks/use-document";
import { useEmployeeLookup } from "@/hooks/use-lookup";
import { reversedPaymentIds } from "@/lib/credit";
import { formatMoney } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { Payment, SalesInvoice } from "@/lib/types";

/**
 * Every row of money the store received against one sale, oldest first.
 *
 * Shared by the two panels that show them: a store-credit sale's payments
 * against its debt, and a counter sale's tenders. The rows are the same
 * shape and reverse the same way; only the figures above them differ.
 */
export function PaymentsTable({ invoice }: { invoice: SalesInvoice }) {
  const t = useTranslations("credit");
  const employees = useEmployeeLookup();
  const reversed = reversedPaymentIds(invoice.payments);

  if (invoice.payments.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        {t("noPayments")}
      </Text>
    );
  }

  return (
    <TableScrollArea>
      <Table verticalSpacing="sm" miw={640}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t("date")}</Table.Th>
            <Table.Th>{t("amount")}</Table.Th>
            <Table.Th>{t("method")}</Table.Th>
            <Table.Th>{t("takenBy")}</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {invoice.payments.map((payment) => (
            <PaymentRow
              key={payment.id}
              payment={payment}
              takenBy={employees.get(payment.userId)}
              isReversed={reversed.has(payment.id)}
            />
          ))}
        </Table.Tbody>
      </Table>
    </TableScrollArea>
  );
}

/** One figure with its label, for the row of totals above a payments table. */
export function Figure({
  label,
  value,
  strong,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <Stack gap="3xs">
      <Text size="xs" c="dimmed" tt="uppercase">
        {label}
      </Text>
      <Text size={strong ? "xl" : "md"} fw={strong ? 700 : 500}>
        {value}
      </Text>
    </Stack>
  );
}


/**
 * One payment. A reversal is shown beside the row it undoes rather than
 * replacing it: the money really did change hands twice, and FR-11.8 keeps
 * both halves.
 */
function PaymentRow({
  payment,
  takenBy,
  isReversed,
}: {
  payment: Payment;
  takenBy: string | undefined;
  isReversed: boolean;
}) {
  const t = useTranslations("credit");
  const tCommon = useTranslations("common");
  const { formatDateTime } = useDateFormat();
  const can = useCan();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  // The route is keyed by the payment, but what comes back is the invoice —
  // so the cache this refreshes is the invoice's, not `["payments"]`.
  const reverse = useDocumentAction<SalesInvoice>("payments", payment.id, {
    path: "/reverse",
    invalidate: false,
  });

  async function run() {
    setError(null);
    try {
      await reverse.mutateAsync(undefined as never);
      await queryClient.invalidateQueries({ queryKey: ["invoices"] });
      notifySuccess(t("reversed"));
    } catch (thrown) {
      setError(errorMessage(thrown, tCommon("retry")));
    }
  }

  const spent = payment.isReversal || isReversed;

  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm">{formatDateTime(payment.occurredAt)}</Text>
      </Table.Td>
      <Table.Td>
        <Group gap="2xs" wrap="nowrap">
          <Text
            size="sm"
            fw={600}
            c={payment.amount.minor < 0 ? "red" : undefined}
            td={isReversed ? "line-through" : undefined}
          >
            {formatMoney(payment.amount)}
          </Text>
          {payment.isReversal && (
            <Badge size="xs" variant="light" color="red">
              {t("reversal")}
            </Badge>
          )}
        </Group>
        {payment.note && (
          <Text size="xs" c="dimmed">
            {payment.note}
          </Text>
        )}
        {error && (
          <Text size="xs" c="red">
            {error}
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        <Text size="sm">{t(`methods.${payment.method}`)}</Text>
      </Table.Td>
      <Table.Td>
        <Text size="sm">{takenBy ?? tCommon("none")}</Text>
      </Table.Td>
      <Table.Td>
        <Group justify="flex-end">
          {!spent && can(Permission.Payment.Reverse) && (
            <Button
              size="compact-sm"
              variant="subtle"
              color="red"
              loading={reverse.isPending}
              onClick={run}
            >
              {t("reverse")}
            </Button>
          )}
        </Group>
      </Table.Td>
    </Table.Tr>
  );
}
