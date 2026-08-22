"use client";

import { Button, Textarea } from "@mantine/core";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { MoneyInput } from "@/components/MoneyInput";
import { useDocumentAction } from "@/hooks/use-document";
import { formatMoney } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import type { SalesInvoice, SalesInvoiceLine } from "@/lib/types";

/**
 * FR-4.5: an Owner or Manager charges something other than what the system
 * resolved, and the override is stamped with their name there and then.
 *
 * `price` and `note` always travel together. The server branches on which
 * keys arrived and then reads `price`, so a body carrying only a note would
 * clear the override — the two are one decision, not two fields.
 *
 * Clearing is its own action because it is not the same as pricing at zero:
 * it hands the line back to resolution, and drops the approver and the note
 * with it.
 */
export function OverridePriceModal({
  invoiceId,
  line,
  resolvedMinor,
  onClose,
}: {
  invoiceId: string;
  line: SalesInvoiceLine;
  resolvedMinor: number | null;
  onClose: () => void;
}) {
  const tSell = useTranslations("invoices.sell");
  const tCommon = useTranslations("common");

  const [price, setPrice] = useState(line.overridePrice ?? "");
  const [note, setNote] = useState(line.priceNote ?? "");
  const [error, setError] = useState<string | null>(null);

  const override = useDocumentAction<
    SalesInvoice,
    { price: string | null; note: string | null }
  >("invoices", invoiceId, {
    method: "PATCH",
    path: () => `/lines/${line.id}`,
  });

  async function send(body: { price: string | null; note: string | null }) {
    setError(null);
    try {
      await override.mutateAsync(body);
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
      title={tSell("overrideTitle")}
      onSubmit={(event) => {
        event.preventDefault();
        send({ price: price.trim() || null, note: note.trim() || null });
      }}
      busy={override.isPending}
      error={error}
      submitLabel={tCommon("save")}
    >
      <MoneyInput
        label={tSell("overridePrice")}
        description={
          resolvedMinor === null
            ? tSell("noResolvedPrice")
            : tSell("resolvedHint", {
                price: formatMoney(resolvedMinor, line.currency),
              })
        }
        value={price}
        onChange={setPrice}
        currency={line.currency}
        data-autofocus
      />
      <Textarea
        label={tSell("overrideNote")}
        description={tSell("overrideNoteHint")}
        value={note}
        onChange={(event) => setNote(event.currentTarget.value)}
        autosize
        minRows={2}
      />
      {line.overridePriceMinor !== null && (
        <Button
          variant="subtle"
          color="red"
          loading={override.isPending}
          onClick={() => send({ price: null, note: null })}
        >
          {tSell("clearOverride")}
        </Button>
      )}
    </FormModal>
  );
}
