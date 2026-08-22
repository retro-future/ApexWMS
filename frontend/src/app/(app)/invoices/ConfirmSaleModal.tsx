"use client";

import {
  Alert,
  Divider,
  List,
  Select,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { useCan } from "@/components/MeProvider";
import { MoneyInput } from "@/components/MoneyInput";
import { Subtotals } from "@/components/Subtotals";
import { useResourceList } from "@/hooks/use-resource";
import {
  confirmBody,
  EMPTY_TERMS,
  somMinor,
  termsBlockers,
  type CreditTerms,
} from "@/lib/credit";
import { formatMoney, isValidPriceInput } from "@/lib/money";
import { Permission } from "@/lib/permissions";
import type {
  CreditCompany,
  Currency,
  PaymentType,
  SalesInvoice,
} from "@/lib/types";

/**
 * How this sale is being paid for, asked at the moment of confirm.
 *
 * The terms live here rather than on the draft because they are only known
 * once the customer has agreed to them: the som debt is a figure the seller
 * quotes in their head for a dollar-priced phone (PRD §4.7), and the down
 * payment is whatever the customer has on them.
 *
 * The quote is shown alongside, because that conversion is the whole
 * transaction and the seller is doing it while looking at this dialog.
 * Nothing here converts anything — no rate is recorded anywhere in the
 * system, by design.
 *
 * `termsBlockers` renders inline rather than as a toast, for the same reason
 * the confirm refusal does: a refusal after the customer has walked away
 * with the phone is useless.
 */
export function ConfirmSaleModal({
  invoice,
  quote,
  busy,
  error,
  onClose,
  onSubmit,
}: {
  invoice: SalesInvoice;
  quote: { currency: Currency; amountMinor: number }[];
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (body: Record<string, unknown>) => void;
}) {
  const t = useTranslations("credit");
  const tInvoices = useTranslations("invoices");
  const tDoc = useTranslations("documents");
  const can = useCan();

  const [terms, setTerms] = useState<CreditTerms>({
    ...EMPTY_TERMS,
    paymentType: invoice.paymentType,
  });

  const mayLend = can(Permission.CreditSale.Create);
  const companies = useResourceList<CreditCompany>(
    "credit-companies",
    { page: 1, pageSize: 200, isActive: true },
    { enabled: mayLend && can(Permission.CreditCompany.View) },
  );

  const blockers = termsBlockers(invoice, terms);
  const debtMinor = somMinor(terms.debt);
  const downMinor = somMinor(terms.downPayment) ?? 0;

  function set<K extends keyof CreditTerms>(key: K, value: CreditTerms[K]) {
    setTerms((current) => ({ ...current, [key]: value }));
  }

  const options: { value: PaymentType; label: string }[] = [
    { value: "paid_in_full", label: t("paidInFull") },
    { value: "credit_company", label: t("creditCompany") },
    { value: "store_credit", label: t("storeCredit") },
  ];

  return (
    <FormModal
      opened
      onClose={onClose}
      title={tInvoices("confirmTitle")}
      busy={busy}
      error={error}
      submitLabel={tDoc("confirmAction")}
      onSubmit={(event) => {
        event.preventDefault();
        if (blockers.length === 0) onSubmit(confirmBody(terms));
      }}
    >
      <Text size="sm" c="dimmed">
        {tInvoices("confirmBody")}
      </Text>

      {quote.length > 0 && (
        <Stack gap="3xs">
          <Text size="sm" c="dimmed">
            {tDoc("quoteHint")}
          </Text>
          <Subtotals subtotals={quote} size="md" fw={600} />
        </Stack>
      )}

      <Divider />

      <Stack gap="3xs">
        <Text size="sm" fw={500}>
          {t("paymentType")}
        </Text>
        <SegmentedControl
          fullWidth
          value={terms.paymentType}
          onChange={(value) => set("paymentType", value as PaymentType)}
          data={options.map((option) => ({
            ...option,
            disabled: option.value !== "paid_in_full" && !mayLend,
          }))}
        />
      </Stack>

      {terms.paymentType === "credit_company" && (
        <>
          <Select
            label={t("company")}
            description={t("companyHint")}
            data={companies.data?.items.map((company) => ({
              value: company.id,
              label: company.name,
            }))}
            value={terms.creditCompanyId}
            onChange={(value) => set("creditCompanyId", value)}
            searchable
            data-autofocus
          />
          <TextInput
            label={t("contractRef")}
            description={t("contractRefHint")}
            value={terms.contractRef}
            onChange={(event) => set("contractRef", event.currentTarget.value)}
          />
        </>
      )}

      {terms.paymentType === "store_credit" && (
        <>
          <MoneyInput
            label={t("debt")}
            description={t("debtHint")}
            value={terms.debt}
            onChange={(value) => set("debt", value)}
            error={
              terms.debt.trim() && !isValidPriceInput(terms.debt, "UZS")
                ? t("somOnly")
                : undefined
            }
            currency="UZS"
            data-autofocus
          />
          <MoneyInput
            label={t("downPayment")}
            description={t("downPaymentHint")}
            value={terms.downPayment}
            onChange={(value) => set("downPayment", value)}
            currency="UZS"
          />
          {debtMinor !== null && debtMinor > 0 && (
            <Text size="sm">
              {t("remainingAfter", {
                amount: formatMoney(Math.max(debtMinor - downMinor, 0), "UZS"),
              })}
            </Text>
          )}
        </>
      )}

      {blockers.length > 0 && (
        <Alert variant="light" color="yellow" icon={<IconAlertCircle size={18} />}>
          <List size="sm">
            {blockers.map((blocker) => (
              <List.Item key={blocker}>{t(`blocker.${blocker}`)}</List.Item>
            ))}
          </List>
        </Alert>
      )}
    </FormModal>
  );
}
