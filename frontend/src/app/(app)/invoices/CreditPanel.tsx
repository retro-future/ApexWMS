"use client";

import {
  Alert,
  Button,
  Card,
  Group,
  Select,
  Stack,
  Text,
  Textarea,
} from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Figure, PaymentsTable } from "@/app/(app)/invoices/PaymentsTable";
import { FormModal } from "@/components/FormModal";
import { useCan } from "@/components/MeProvider";
import { MoneyInput } from "@/components/MoneyInput";
import { useDocumentAction } from "@/hooks/use-document";
import { refundDueMinor } from "@/lib/credit";
import { formatMoney, formatMoneyOrDash, isValidPriceInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { PaymentMethod, SalesInvoice } from "@/lib/types";
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

  const [recording, setRecording] = useState(false);

  const refund = refundDueMinor(invoice);
  const settled = invoice.status === "confirmed" && invoice.remaining.minor === 0;

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
            invoice.remaining.minor > 0 &&
            can(Permission.Payment.Record) && (
              <Button variant="light" onClick={() => setRecording(true)}>
                {t("recordPayment")}
              </Button>
            )}
        </Group>

        <Group gap="xl" wrap="wrap">
          <Figure label={t("debt")} value={formatMoneyOrDash(invoice.debt)} />
          <Figure label={t("paid")} value={formatMoney(invoice.paid)} />
          {invoice.relieved.minor > 0 && (
            <Figure label={t("relieved")} value={formatMoney(invoice.relieved)} />
          )}
          <Figure
            label={t("remaining")}
            value={formatMoney(invoice.remaining)}
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
            {t("refundDue", { amount: formatMoney({ minor: refund, currency: "UZS" }) })}
          </Alert>
        )}

        <PaymentsTable invoice={invoice} />
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
  const tooMuch = !malformed && Number(amount.trim() || 0) > invoice.remaining.minor;

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
          amount: formatMoney(invoice.remaining),
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
