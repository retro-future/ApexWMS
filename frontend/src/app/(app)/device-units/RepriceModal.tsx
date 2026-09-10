"use client";

import { Textarea } from "@mantine/core";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { MoneyInput } from "@/components/MoneyInput";
import { useDocumentAction } from "@/hooks/use-document";
import { isValidPriceInput, moneyToInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import type { DeviceUnit } from "@/lib/types";

/** FR-2.15/FR-2.16: a cut is an append-only row, never an overwrite. */
export function RepriceModal({
  unit,
  onClose,
}: {
  unit: DeviceUnit;
  onClose: () => void;
}) {
  const t = useTranslations("deviceUnits");
  const tCommon = useTranslations("common");
  const tDoc = useTranslations("documents");

  const [price, setPrice] = useState(moneyToInput(unit.askingPrice));
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reprice = useDocumentAction<
    DeviceUnit,
    { askingPrice: string; reason: string | null }
  >("device-units", unit.id, { method: "PATCH", path: "/price" });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!isValidPriceInput(price, unit.currency)) {
      setError(
        unit.currency === "USD" ? tDoc("priceHintUsd") : tDoc("priceHintUzs"),
      );
      return;
    }
    try {
      await reprice.mutateAsync({
        askingPrice: price.trim(),
        reason: reason.trim() || null,
      });
      notifySuccess(t("repriced"));
      onClose();
    } catch (thrown) {
      setError(errorMessage(thrown, tCommon("retry")));
    }
  }

  return (
    <FormModal
      opened
      onClose={onClose}
      title={t("repriceTitle")}
      onSubmit={submit}
      busy={reprice.isPending}
      error={error}
      submitLabel={tCommon("save")}
    >
      <MoneyInput
        label={t("newPrice")}
        description={t("repriceHint")}
        value={price}
        onChange={setPrice}
        currency={unit.currency}
        data-autofocus
      />
      <Textarea
        label={tDoc("reason")}
        value={reason}
        onChange={(event) => setReason(event.currentTarget.value)}
        autosize
        minRows={2}
      />
    </FormModal>
  );
}
