"use client";

import { NumberInput, Textarea } from "@mantine/core";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { MoneyInput } from "@/components/MoneyInput";
import { useDocumentAction } from "@/hooks/use-document";
import { isSerialLine } from "@/lib/customer-returns";
import { formatMoney } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import type { CustomerReturn, CustomerReturnLine } from "@/lib/types";

/**
 * FR-4.9c: a Manager keeps part of what the customer paid, and signs for it.
 *
 * `refund` and `note` always travel together, the way an invoice override's
 * price and note do: keeping money is one decision, not two fields. The
 * server stamps the approver from the token and refuses a reduction with no
 * note, so there is nothing to send separately.
 *
 * The quantity sits in the same modal for an accessory line, because
 * correcting a mis-scanned count by unscanning and re-scanning three times
 * is the workflow §6 exists to avoid. A serialized line has no count to
 * correct — it is one named handset.
 */
export function RefundModal({
  returnId,
  line,
  onClose,
}: {
  returnId: string;
  line: CustomerReturnLine;
  onClose: () => void;
}) {
  const t = useTranslations("customerReturns");
  const tCommon = useTranslations("common");

  const [refund, setRefund] = useState(line.refundPrice);
  const [note, setNote] = useState(line.refundNote ?? "");
  const [quantity, setQuantity] = useState<number>(line.quantity);
  const [error, setError] = useState<string | null>(null);

  const save = useDocumentAction<
    CustomerReturn,
    { refund?: string; note?: string; quantity?: number }
  >("customer-returns", returnId, {
    method: "PATCH",
    path: () => `/lines/${line.id}`,
  });

  const serial = isSerialLine(line);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await save.mutateAsync({
        refund: refund.trim() || undefined,
        note: note.trim() || undefined,
        ...(serial ? {} : { quantity }),
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
      title={t("refundTitle")}
      onSubmit={submit}
      busy={save.isPending}
      error={error}
      submitLabel={tCommon("save")}
    >
      <MoneyInput
        label={t("refund")}
        description={t("refundHint", {
          charged: formatMoney(line.chargedPriceMinor, line.currency),
        })}
        value={refund}
        onChange={setRefund}
        currency={line.currency}
        data-autofocus
      />
      {!serial && (
        <NumberInput
          label={t("quantity")}
          description={t("quantityHint", { sold: line.soldQuantity })}
          value={quantity}
          onChange={(value) => setQuantity(Number(value) || 1)}
          min={1}
          max={line.soldQuantity}
          allowDecimal={false}
        />
      )}
      <Textarea
        label={t("refundNote")}
        description={t("refundNoteHint")}
        value={note}
        onChange={(event) => setNote(event.currentTarget.value)}
        autosize
        minRows={2}
      />
    </FormModal>
  );
}
