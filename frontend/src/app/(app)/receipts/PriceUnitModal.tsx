"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { MoneyInput } from "@/components/MoneyInput";
import { useDocumentAction } from "@/hooks/use-document";
import { useCurrentRates } from "@/hooks/use-exchange-rates";
import { formatMoney, inputToMoney, moneyToInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { somAtRate } from "@/lib/rates";
import type { ReferenceCost } from "@/lib/receipts";
import type { ReceivedUnit } from "@/lib/types";

/** FR-3.4b: an Owner or Manager prices what the Storekeeper scanned. */
export function PriceUnitModal({
  receiptId,
  unit,
  reference,
  isTradeIn,
  onClose,
}: {
  receiptId: string;
  unit: ReceivedUnit;
  reference: ReferenceCost | undefined;
  isTradeIn: boolean;
  onClose: () => void;
}) {
  const tScan = useTranslations("receipts.scan");
  const tCommon = useTranslations("common");
  const tRates = useTranslations("rates");
  const rates = useCurrentRates();

  const [cost, setCost] = useState(moneyToInput(unit.acquisitionCost ?? reference));
  const [asking, setAsking] = useState(moneyToInput(unit.askingPrice));
  const [cash, setCash] = useState("");
  const [error, setError] = useState<string | null>(null);
  const valued = inputToMoney(cost, unit.currency);
  const atRate = somAtRate(
    valued ? [valued] : [],
    rates.data?.buyback?.somPerUsd ?? null,
  );

  const price = useDocumentAction<
    ReceivedUnit,
    {
      acquisitionCost?: string;
      askingPrice?: string;
      cashPaid?: string;
      cashPaidCurrency?: "UZS";
    }
  >("receipts", receiptId, {
    method: "PATCH",
    path: () => `/scan/${unit.imei}`,
  });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await price.mutateAsync({
        ...(cost.trim() ? { acquisitionCost: cost.trim() } : {}),
        ...(asking.trim() ? { askingPrice: asking.trim() } : {}),
        ...(cash.trim() ? { cashPaid: cash.trim(), cashPaidCurrency: "UZS" } : {}),
      });
      notifySuccess(tCommon("saved"));
      onClose();
    } catch (thrown) {
      setError(errorMessage(thrown, tCommon("retry")));
    }
  }

  return (
    <FormModal
      opened
      onClose={onClose}
      title={tScan("priceUnitTitle", { imei: unit.imei })}
      onSubmit={submit}
      busy={price.isPending}
      error={error}
      submitLabel={tCommon("save")}
    >
      <MoneyInput
        label={tScan("acquisitionCost")}
        description={
          !unit.acquisitionCost && reference
            ? tScan("poReferenceHint", {
                price: formatMoney(reference),
              })
            : undefined
        }
        value={cost}
        onChange={setCost}
        currency={unit.currency}
        data-autofocus
      />
      <MoneyInput
        label={tScan("askingPrice")}
        value={asking}
        onChange={setAsking}
        currency={unit.currency}
      />
      {/* A trade-in cannot be confirmed without it (W9 B2): the som is the
          only record of what the store actually paid out. */}
      <MoneyInput
        label={tScan("cashPaid")}
        description={
          isTradeIn && atRate !== null
            ? tRates("atRate", {
                amount: formatMoney({ minor: atRate, currency: "UZS" }),
                rate: rates.data?.buyback?.somPerUsd ?? "",
              })
            : tScan("cashPaidHint")
        }
        value={cash}
        onChange={setCash}
        currency="UZS"
        required={isTradeIn}
      />
    </FormModal>
  );
}
