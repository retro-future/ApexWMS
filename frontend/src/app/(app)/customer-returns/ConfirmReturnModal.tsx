"use client";

import { Alert, Stack, Text } from "@mantine/core";
import { IconInfoCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { MoneyInput } from "@/components/MoneyInput";
import { Subtotals } from "@/components/Subtotals";
import { formatMoney } from "@/lib/money";
import type { CustomerReturn } from "@/lib/types";

/**
 * FR-4.9f, and FR-4.9d where the sale was on store credit.
 *
 * The relief is entered here rather than when the return is opened, for the
 * same reason a sale takes its payment terms at confirm: what is still owed
 * moves while a draft sits open, and a figure typed earlier would be capped
 * against a balance that has since changed.
 *
 * It is a **som** figure the manager states, never a conversion of the
 * refund subtotals above it. Those are in the products' own currencies, and
 * converting between them would need a rate this system deliberately does
 * not have (§4.7).
 */
export function ConfirmReturnModal({
  document,
  outstandingMinor,
  onClose,
  onSubmit,
  busy,
  error,
}: {
  document: CustomerReturn;
  /** The sale's remaining som balance, or null when it opened no debt. */
  outstandingMinor: number | null;
  onClose: () => void;
  onSubmit: (debtRelief: string | null) => void;
  busy?: boolean;
  error?: string | null;
}) {
  const t = useTranslations("customerReturns");
  const tDoc = useTranslations("documents");

  const owesSomething = outstandingMinor !== null && outstandingMinor > 0;
  const [relief, setRelief] = useState(
    owesSomething ? String(outstandingMinor) : "",
  );

  return (
    <FormModal
      opened
      onClose={onClose}
      title={t("confirmTitle")}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(owesSomething ? relief.trim() || null : null);
      }}
      busy={busy}
      error={error}
      submitLabel={tDoc("confirmAction")}
    >
      <Text size="sm" c="dimmed">
        {t("confirmBody")}
      </Text>

      <Stack gap="2xs">
        <Text size="sm" fw={500}>
          {t("refunded")}
        </Text>
        <Subtotals subtotals={document.subtotals} fw={600} />
      </Stack>

      {owesSomething && (
        <>
          <MoneyInput
            label={t("debtRelief")}
            description={t("debtReliefHint", {
              outstanding: formatMoney({ minor: outstandingMinor, currency: "UZS" }),
            })}
            value={relief}
            onChange={setRelief}
            currency="UZS"
            data-autofocus
          />
          <Alert variant="light" color="blue" icon={<IconInfoCircle size={18} />}>
            {t("debtReliefNotice")}
          </Alert>
        </>
      )}
    </FormModal>
  );
}
