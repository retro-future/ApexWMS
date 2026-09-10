"use client";

import { ActionIcon, Badge, Button, Group, NumberInput, Stack, Table, Text } from "@mantine/core";
import { IconTrash } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { useCan } from "@/components/MeProvider";
import { useDocumentAction } from "@/hooks/use-document";
import { isSerial, type QuoteMap } from "@/lib/invoices";
import { formatMoney } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { SalesInvoice, SalesInvoiceLine } from "@/lib/types";

/**
 * One line, in both of the states it can be read in: a draft showing the
 * quote this screen assembled, and a confirmed invoice showing the snapshot
 * the server took at confirm (FR-4.5b).
 */
export function InvoiceLineRow({
  line,
  invoiceId,
  draft,
  quotes,
  productName,
  approver,
  onOverride,
  onError,
}: {
  line: SalesInvoiceLine;
  invoiceId: string;
  draft: boolean;
  quotes: QuoteMap;
  productName: string | undefined;
  approver: string | undefined;
  onOverride: () => void;
  onError: (message: string) => void;
}) {
  const t = useTranslations("invoices");
  const tSell = useTranslations("invoices.sell");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const can = useCan();

  // Both close over this line, so the id stays in the URL where it belongs
  // rather than riding along in a body the endpoint does not declare.
  const remove = useDocumentAction<SalesInvoice>("invoices", invoiceId, {
    method: "DELETE",
    path: `/lines/${line.id}`,
  });
  const requantify = useDocumentAction<SalesInvoice, { quantity: number }>(
    "invoices",
    invoiceId,
    { method: "PATCH", path: `/lines/${line.id}` },
  );
  const busy = remove.isPending || requantify.isPending;

  async function run(action: Promise<unknown>, done?: () => void) {
    try {
      await action;
      done?.();
    } catch (error) {
      onError(errorMessage(error, tCommon("retry")));
    }
  }

  const quote = quotes.get(line.id);
  const resolvedMinor = draft ? (quote?.resolvedMinor ?? null) : (line.resolvedPrice?.minor ?? null);
  const charged = draft ? (quote?.chargedMinor ?? null) : (line.chargedPrice?.minor ?? null);
  const deviates = draft
    ? line.overridePrice !== null && line.overridePrice.minor !== resolvedMinor
    : line.isDeviation;

  return (
    <Table.Tr>
      <Table.Td>
        <Stack gap="3xs">
          <Text size="sm">{productName ?? tCommon("none")}</Text>
          {!isSerial(line) && (
            <Text size="xs" c="dimmed">
              {tSell("accessory")}
            </Text>
          )}
        </Stack>
      </Table.Td>
      <Table.Td>
        {draft && !isSerial(line) && can(Permission.Sales.Manage) ? (
          <NumberInput
            value={line.quantity}
            onChange={(value) => run(requantify.mutateAsync({ quantity: Number(value) || 1 }))}
            min={1}
            allowDecimal={false}
            disabled={busy}
            w={90}
            aria-label={tDoc("quantity")}
          />
        ) : (
          line.quantity
        )}
      </Table.Td>
      <Table.Td>
        {resolvedMinor === null ? (
          <Badge size="xs" variant="light" color="yellow">
            {tSell("needsPrice")}
          </Badge>
        ) : (
          <Text
            size="sm"
            td={deviates ? "line-through" : undefined}
            c={deviates ? "dimmed" : undefined}
          >
            {formatMoney({ minor: resolvedMinor, currency: line.currency })}
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        {charged === null ? (
          tCommon("none")
        ) : (
          <Stack gap="3xs">
            <Text size="sm" fw={deviates ? 600 : undefined}>
              {formatMoney({ minor: charged, currency: line.currency })}
            </Text>
            {deviates && (
              <Text size="xs" c="dimmed">
                {/* FR-4.5f: the approver is whoever overrode it, which need
                    not be whoever confirmed the invoice. */}
                {approver ? tDoc("approvedBy", { name: approver }) : t("approvedBySomeone")}
                {line.priceNote && ` — ${line.priceNote}`}
              </Text>
            )}
          </Stack>
        )}
      </Table.Td>
      <Table.Td>
        <Group gap="2xs" justify="flex-end" wrap="nowrap">
          {draft && can(Permission.Pricing.Override) && (
            <Button size="compact-sm" variant="subtle" onClick={onOverride}>
              {tSell("override")}
            </Button>
          )}
          {draft && can(Permission.Sales.Manage) && (
            <ActionIcon
              variant="subtle"
              color="red"
              aria-label={tSell("remove")}
              loading={busy}
              onClick={() => run(remove.mutateAsync(undefined as never), () => notifySuccess(tSell("removed")))}
            >
              <IconTrash size={16} />
            </ActionIcon>
          )}
        </Group>
      </Table.Td>
    </Table.Tr>
  );
}
