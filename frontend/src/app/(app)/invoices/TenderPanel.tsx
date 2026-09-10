"use client";

import { Button, Card, Group, Select, Stack, Text, Textarea } from "@mantine/core";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { PaymentsTable } from "@/app/(app)/invoices/PaymentsTable";
import { FormModal } from "@/components/FormModal";
import { useCan } from "@/components/MeProvider";
import { MoneyInput } from "@/components/MoneyInput";
import { Subtotals } from "@/components/Subtotals";
import { useDocumentAction } from "@/hooks/use-document";
import { isValidPriceInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { Currency, PaymentMethod, SalesInvoice } from "@/lib/types";
import { CURRENCIES, PAYMENT_METHODS } from "@/lib/types";

/**
 * What the customer actually handed over on a sale settled at the counter.
 *
 * Deliberately shown next to the sale's own subtotals rather than compared
 * with them: a $600 handset paid for in som is two true figures and no rate
 * links them (§4.5 rule 1). The panel never says whether the tender "covers"
 * the sale, because answering that would need the conversion this system
 * does not have — the seller works it out, and the till proves it at the end
 * of the shift.
 */
export function TenderPanel({ invoice }: { invoice: SalesInvoice }) {
  const t = useTranslations("credit");
  const tDoc = useTranslations("documents");
  const can = useCan();
  const [recording, setRecording] = useState(false);

  return (
    <Card withBorder radius="md" padding="lg">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Stack gap="3xs">
            <Text fw={500}>{t("tenderTitle")}</Text>
            <Text size="sm" c="dimmed">
              {t("tenderHint")}
            </Text>
          </Stack>
          {invoice.status === "confirmed" && can(Permission.Payment.Record) && (
            <Button variant="light" onClick={() => setRecording(true)}>
              {t("recordTender")}
            </Button>
          )}
        </Group>

        <Group gap="xl" wrap="wrap" align="flex-start">
          <Stack gap="3xs">
            <Text size="xs" c="dimmed" tt="uppercase">
              {tDoc("subtotals")}
            </Text>
            <Subtotals subtotals={invoice.subtotals} size="md" fw={600} />
          </Stack>
          <Stack gap="3xs">
            <Text size="xs" c="dimmed" tt="uppercase">
              {t("tendered")}
            </Text>
            <Subtotals subtotals={invoice.tendered} size="md" fw={600} />
          </Stack>
        </Group>

        <PaymentsTable invoice={invoice} />
      </Stack>

      {recording && (
        <RecordTenderModal invoice={invoice} onClose={() => setRecording(false)} />
      )}
    </Card>
  );
}

/** Money over the counter. No cap: the sale opened no debt to overpay. */
function RecordTenderModal({
  invoice,
  onClose,
}: {
  invoice: SalesInvoice;
  onClose: () => void;
}) {
  const t = useTranslations("credit");
  const tCommon = useTranslations("common");
  const tDoc = useTranslations("documents");

  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState<Currency>("UZS");
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const record = useDocumentAction<
    SalesInvoice,
    {
      amount: string;
      currency: Currency;
      method: PaymentMethod;
      note: string | null;
    }
  >("invoices", invoice.id, { path: "/payments" });

  const malformed = Boolean(amount.trim()) && !isValidPriceInput(amount, currency);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!amount.trim() || malformed) return;
    setError(null);
    try {
      await record.mutateAsync({
        amount: amount.trim(),
        currency,
        method,
        note: note.trim() || null,
      });
      notifySuccess(t("tenderRecorded"));
      onClose();
    } catch (thrown) {
      setError(errorMessage(thrown, tCommon("retry")));
    }
  }

  return (
    <FormModal
      opened
      onClose={onClose}
      title={t("recordTender")}
      onSubmit={submit}
      busy={record.isPending}
      error={error}
      submitLabel={t("recordTender")}
    >
      <Select
        label={t("currency")}
        value={currency}
        onChange={(value) => setCurrency((value as Currency) ?? "UZS")}
        allowDeselect={false}
        data={[...CURRENCIES]}
      />
      <MoneyInput
        label={t("amount")}
        description={t("tenderAmountHint")}
        value={amount}
        onChange={setAmount}
        error={
          malformed
            ? currency === "USD"
              ? tDoc("priceHintUsd")
              : tDoc("priceHintUzs")
            : undefined
        }
        currency={currency}
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
