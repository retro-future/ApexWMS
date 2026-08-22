"use client";

import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
} from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { useCan } from "@/components/MeProvider";
import { MoneyInput } from "@/components/MoneyInput";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useDateFormat } from "@/hooks/use-date-format";
import { useDocumentAction } from "@/hooks/use-document";
import { useEmployeeLookup } from "@/hooks/use-lookup";
import { refundDueMinor, reversedPaymentIds } from "@/lib/credit";
import { formatMoney, isValidPriceInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { Payment, PaymentMethod, SalesInvoice } from "@/lib/types";
import { PAYMENT_METHODS } from "@/lib/types";

/**
 * What the customer owes on this sale, and everything they have paid.
 *
 * Three figures, and only the first is stored: the som debt the seller wrote
 * at the counter. `paid` and `remaining` are recomputed from the payment rows
 * on every read (PRD §4.7), which is why nothing here caches them.
 *
 * On a **cancelled** sale the remaining balance is zero and the payments are
 * still listed. That is FR-11.11: the debt is void, the money the customer
 * handed over is not, and somebody has to give it back.
 */
export function CreditPanel({ invoice }: { invoice: SalesInvoice }) {
  const t = useTranslations("credit");
  const can = useCan();
  const employees = useEmployeeLookup();

  const [recording, setRecording] = useState(false);

  const debtMinor = invoice.debtMinor ?? 0;
  const refund = refundDueMinor(invoice);
  const reversed = reversedPaymentIds(invoice.payments);
  const settled = invoice.status === "confirmed" && invoice.remainingMinor === 0;

  return (
    <Card withBorder radius="md" padding="lg">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Stack gap="3xs">
            <Text fw={500}>{t("panelTitle")}</Text>
            <Text size="sm" c="dimmed">
              {t("panelHint")}
            </Text>
          </Stack>
          {/* Nothing left to pay means nothing to record: the server refuses
              a payment above the balance (FR-11.6), and a settled sale's is
              zero. Reversing one reopens it and the button comes back. */}
          {invoice.status === "confirmed" &&
            invoice.remainingMinor > 0 &&
            can(Permission.Payment.Record) && (
              <Button variant="light" onClick={() => setRecording(true)}>
                {t("recordPayment")}
              </Button>
            )}
        </Group>

        <Group gap="xl" wrap="wrap">
          <Figure label={t("debt")} value={formatMoney(debtMinor, "UZS")} />
          <Figure label={t("paid")} value={formatMoney(invoice.paidMinor, "UZS")} />
          <Figure
            label={t("remaining")}
            value={formatMoney(invoice.remainingMinor, "UZS")}
            strong
          />
        </Group>

        {settled && (
          <Alert variant="light" color="teal">
            {t("settled")}
          </Alert>
        )}

        {refund > 0 && (
          <Alert variant="light" color="orange" icon={<IconAlertCircle size={18} />}>
            {t("refundDue", { amount: formatMoney(refund, "UZS") })}
          </Alert>
        )}

        {invoice.payments.length === 0 ? (
          <Text size="sm" c="dimmed">
            {t("noPayments")}
          </Text>
        ) : (
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
        )}
      </Stack>

      {recording && (
        <RecordPaymentModal
          invoice={invoice}
          onClose={() => setRecording(false)}
        />
      )}
    </Card>
  );
}

function Figure({
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
            c={payment.amountMinor < 0 ? "red" : undefined}
            td={isReversed ? "line-through" : undefined}
          >
            {formatMoney(payment.amountMinor, "UZS")}
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

/** FR-11.6: money off what is still owed, refused above the balance. */
function RecordPaymentModal({
  invoice,
  onClose,
}: {
  invoice: SalesInvoice;
  onClose: () => void;
}) {
  const t = useTranslations("credit");
  const tCommon = useTranslations("common");

  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const record = useDocumentAction<
    SalesInvoice,
    { amount: string; method: PaymentMethod; note: string | null }
  >("invoices", invoice.id, { path: "/payments" });

  const malformed = Boolean(amount.trim()) && !isValidPriceInput(amount, "UZS");
  const tooMuch = !malformed && Number(amount.trim() || 0) > invoice.remainingMinor;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!amount.trim() || malformed || tooMuch) return;
    setError(null);
    try {
      await record.mutateAsync({
        amount: amount.trim(),
        method,
        note: note.trim() || null,
      });
      notifySuccess(t("paymentRecorded"));
      onClose();
    } catch (thrown) {
      setError(errorMessage(thrown, tCommon("retry")));
    }
  }

  return (
    <FormModal
      opened
      onClose={onClose}
      title={t("recordPayment")}
      onSubmit={submit}
      busy={record.isPending}
      error={error}
      submitLabel={t("recordPayment")}
    >
      <MoneyInput
        label={t("amount")}
        description={t("remainingIs", {
          amount: formatMoney(invoice.remainingMinor, "UZS"),
        })}
        value={amount}
        onChange={setAmount}
        error={malformed ? t("somOnly") : tooMuch ? t("blocker.overpayment") : undefined}
        currency="UZS"
        data-autofocus
      />
      <Select
        label={t("method")}
        description={t("methodHint")}
        value={method}
        onChange={(value) => setMethod((value as PaymentMethod) ?? "cash")}
        data={PAYMENT_METHODS.map((value) => ({
          value,
          label: t(`methods.${value}`),
        }))}
      />
      <Textarea
        label={`${t("note")} (${tCommon("optional")})`}
        value={note}
        onChange={(event) => setNote(event.currentTarget.value)}
        autosize
        minRows={2}
      />
    </FormModal>
  );
}
