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
import { overTheSale, standingCurrencies } from "@/lib/credit";
import { formatMoney, isValidPriceInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import { impliedRate } from "@/lib/rates";
import type { Currency, PaymentMethod, SalesInvoice } from "@/lib/types";
import { CURRENCIES, PAYMENT_METHODS } from "@/lib/types";

/**
 * What the customer actually handed over on a sale settled at the counter.
 *
 * The sale's own subtotals sit beside it, and neither figure is netted
 * against the other: a $600 handset paid for in som is two true facts
 * (§4.5 rule 1). What the panel does show is the two rates around them —
 * what the store was quoting at confirm, and what this sale actually worked
 * out at (W9 B1). A gap between them is a discount nobody recorded, and
 * seeing it is the whole reason the rate is now written down.
 */
export function TenderPanel({ invoice }: { invoice: SalesInvoice }) {
  const t = useTranslations("credit");
  const tDoc = useTranslations("documents");
  const tRates = useTranslations("rates");
  const can = useCan();
  const [recording, setRecording] = useState(false);
  const struck = impliedRate(invoice.subtotals, invoice.tendered);
  const taken = standingCurrencies(invoice.payments);
  const free = CURRENCIES.filter((currency) => !taken.has(currency));

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
          {/* One row per currency. Nothing caps a tender, so a second row in
              a currency already recorded would quietly double what the sale
              took; correcting it is a reversal, then a fresh row. */}
          {invoice.status === "confirmed" &&
            can(Permission.Payment.Record) &&
            (free.length === 0 ? (
              <Text size="sm" c="dimmed" maw={280} ta="right">
                {t("tenderCorrectHint")}
              </Text>
            ) : (
              <Button variant="light" onClick={() => setRecording(true)}>
                {t("recordTender")}
              </Button>
            ))}
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
          {invoice.saleRate && (
            <Stack gap="3xs">
              <Text size="xs" c="dimmed" tt="uppercase">
                {tRates("onSale")}
              </Text>
              <Text size="md" fw={600}>
                {invoice.saleRate.somPerUsd}
              </Text>
            </Stack>
          )}
          {struck !== null && (
            <Stack gap="3xs">
              <Text size="xs" c="dimmed" tt="uppercase">
                {tRates("struckAt")}
              </Text>
              <Text size="md" fw={600}>
                {formatMoney({ minor: Math.round(struck), currency: "UZS" })}
              </Text>
            </Stack>
          )}
        </Group>

        <PaymentsTable invoice={invoice} />
      </Stack>

      {recording && (
        <RecordTenderModal
          invoice={invoice}
          offered={free}
          onClose={() => setRecording(false)}
        />
      )}
    </Card>
  );
}

/** Money over the counter. No cap on the amount, only on the row count. */
function RecordTenderModal({
  invoice,
  offered,
  onClose,
}: {
  invoice: SalesInvoice;
  offered: Currency[];
  onClose: () => void;
}) {
  const t = useTranslations("credit");
  const tCommon = useTranslations("common");
  const tDoc = useTranslations("documents");

  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState<Currency>(offered[0]);
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
  const tooLarge = !malformed && overTheSale(invoice, amount, currency);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!amount.trim() || malformed || tooLarge) return;
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
        onChange={(value) => setCurrency((value as Currency) ?? offered[0])}
        allowDeselect={false}
        data={offered}
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
            : tooLarge
              ? t("blocker.tenderTooLarge")
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
