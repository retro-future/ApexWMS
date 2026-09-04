"use client";

import { ActionIcon, Badge, Group, Table, Text, Tooltip } from "@mantine/core";
import { IconPencil, IconTrash } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { TableScrollArea } from "@/components/TableScrollArea";
import { useProductLookup } from "@/hooks/use-lookup";
import { isSerialLine, keptOnLine } from "@/lib/customer-returns";
import { formatMoney } from "@/lib/money";
import type { CustomerReturnLine } from "@/lib/types";

/**
 * The lines of a customer return, with the money on them.
 *
 * This is where it parts company with `RemovalLinesTable`: a removal carries
 * no figure at all, while a return carries the price somebody agreed to pay
 * back. The charged price sits beside it so a reduction is visible as a
 * reduction rather than as a number the reader has to remember.
 */
export function CustomerReturnLines({
  lines,
  emptyMessage,
  onRemove,
  onEditRefund,
  removeLabel,
  editLabel,
  removing,
}: {
  lines: CustomerReturnLine[];
  emptyMessage: string;
  /** Both omitted once the document is no longer a draft. */
  onRemove?: (imei: string) => void;
  onEditRefund?: (line: CustomerReturnLine) => void;
  removeLabel?: string;
  editLabel?: string;
  removing?: boolean;
}) {
  const t = useTranslations("customerReturns");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const products = useProductLookup();

  if (lines.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        {emptyMessage}
      </Text>
    );
  }

  const editable = onRemove !== undefined || onEditRefund !== undefined;

  return (
    <TableScrollArea>
      <Table verticalSpacing="sm" miw={760}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{tDoc("product")}</Table.Th>
            <Table.Th>IMEI</Table.Th>
            <Table.Th>{tDoc("quantity")}</Table.Th>
            <Table.Th>{t("charged")}</Table.Th>
            <Table.Th>{t("refund")}</Table.Th>
            <Table.Th>{t("kept")}</Table.Th>
            {editable && <Table.Th />}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {lines.map((line) => {
            const kept = keptOnLine(line);
            return (
              <Table.Tr key={line.id}>
                <Table.Td>
                  {products.get(line.productId) ?? tCommon("none")}
                </Table.Td>
                <Table.Td>
                  {line.imei === null ? (
                    <Text size="sm" c="dimmed">
                      {tCommon("none")}
                    </Text>
                  ) : (
                    <Text size="sm" ff="monospace">
                      {line.imei}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  {line.quantity}
                  {!isSerialLine(line) && (
                    <Text span size="xs" c="dimmed">
                      {` / ${line.soldQuantity}`}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {formatMoney(line.chargedPriceMinor, line.currency)}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs" wrap="nowrap">
                    <Text size="sm" fw={line.isReduced ? 600 : 400}>
                      {formatMoney(line.refundPriceMinor, line.currency)}
                    </Text>
                    {line.isReduced && line.refundNote && (
                      <Tooltip label={line.refundNote} withArrow>
                        <Badge size="xs" variant="light" color="orange">
                          {t("reduced")}
                        </Badge>
                      </Tooltip>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>
                  {kept === 0 ? (
                    <Text size="sm" c="dimmed">
                      —
                    </Text>
                  ) : (
                    <Text size="sm" c="orange">
                      {formatMoney(kept, line.currency)}
                    </Text>
                  )}
                </Table.Td>
                {editable && (
                  <Table.Td>
                    <Group gap="2xs" justify="flex-end" wrap="nowrap">
                      {onEditRefund && (
                        <ActionIcon
                          variant="subtle"
                          aria-label={editLabel}
                          onClick={() => onEditRefund(line)}
                        >
                          <IconPencil size={16} />
                        </ActionIcon>
                      )}
                      {/* Unscan names the IMEI, so an accessory line has no
                          button — its count is corrected on the refund
                          screen instead. */}
                      {onRemove && isSerialLine(line) && line.imei !== null && (
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          aria-label={removeLabel}
                          loading={removing}
                          onClick={() => onRemove(line.imei!)}
                        >
                          <IconTrash size={16} />
                        </ActionIcon>
                      )}
                    </Group>
                  </Table.Td>
                )}
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </TableScrollArea>
  );
}
