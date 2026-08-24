"use client";

import { NumberInput, Table, Text } from "@mantine/core";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { TableScrollArea } from "@/components/TableScrollArea";
import { useDocumentAction } from "@/hooks/use-document";
import { useProductLookup } from "@/hooks/use-lookup";
import { errorMessage } from "@/lib/notify";
import { lineDelta } from "@/lib/stock-counts";
import type { StockCount, StockCountLine } from "@/lib/types";

/**
 * The accessory half of a count (FR-6.2): a typed figure per level, not a
 * scan.
 *
 * **An empty cell is not a zero.** `countedQuantity` stays null until
 * somebody states a figure, and a shelf nobody looked at means something
 * different from a shelf found empty — only the second books a loss. So
 * clearing the input sends nothing, and typing `0` is a real count.
 */
export function CountLineTable({
  count,
  editable,
  onCounted,
  onError,
}: {
  count: StockCount;
  editable: boolean;
  onCounted: (updated: StockCount) => void;
  onError: (message: string | null) => void;
}) {
  const t = useTranslations("stockCounts");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const products = useProductLookup();
  const [pending, setPending] = useState<string | null>(null);

  const countLine = useDocumentAction<
    StockCount,
    { lineId: string; countedQuantity: number }
  >("stock-counts", count.id, {
    method: "PATCH",
    path: (payload) => `/lines/${payload.lineId}`,
  });

  if (count.lines.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        {t("noLines")}
      </Text>
    );
  }

  async function submitCount(line: StockCountLine, value: number) {
    onError(null);
    setPending(line.id);
    try {
      const updated = await countLine.mutateAsync({
        lineId: line.id,
        countedQuantity: value,
      });
      if (updated) onCounted(updated);
    } catch (error) {
      onError(errorMessage(error, tCommon("retry")));
    } finally {
      setPending(null);
    }
  }

  return (
    <TableScrollArea>
      <Table verticalSpacing="sm" miw={560}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{tDoc("product")}</Table.Th>
            <Table.Th>{t("expected")}</Table.Th>
            <Table.Th w={160}>{t("counted")}</Table.Th>
            <Table.Th>{t("delta")}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {count.lines.map((line) => {
            const delta = lineDelta(line);
            return (
              <Table.Tr key={line.id}>
                <Table.Td>
                  {products.get(line.productId) ?? tCommon("none")}
                </Table.Td>
                <Table.Td>{line.expectedQuantity}</Table.Td>
                <Table.Td>
                  {editable ? (
                    <NumberInput
                      value={line.countedQuantity ?? ""}
                      onChange={(value) => {
                        // Cleared means uncounted, and there is no endpoint
                        // for un-stating a figure — so send nothing.
                        if (value === "" || value === null) return;
                        void submitCount(line, Number(value));
                      }}
                      min={0}
                      allowDecimal={false}
                      allowNegative={false}
                      disabled={pending === line.id}
                      placeholder={t("uncounted")}
                      aria-label={t("countedFor", {
                        product: products.get(line.productId) ?? "",
                      })}
                    />
                  ) : line.countedQuantity === null ? (
                    <Text size="sm" c="dimmed">
                      {t("uncounted")}
                    </Text>
                  ) : (
                    <Text size="sm">{line.countedQuantity}</Text>
                  )}
                </Table.Td>
                <Table.Td>
                  {delta === null ? (
                    <Text size="sm" c="dimmed">
                      {tCommon("none")}
                    </Text>
                  ) : (
                    <Text
                      size="sm"
                      c={delta === 0 ? "dimmed" : delta > 0 ? "teal" : "orange"}
                    >
                      {delta > 0 ? `+${delta}` : delta}
                    </Text>
                  )}
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </TableScrollArea>
  );
}
