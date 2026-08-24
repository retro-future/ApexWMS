"use client";

import { ActionIcon, Group, Table, Text } from "@mantine/core";
import { IconTrash } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { TableScrollArea } from "@/components/TableScrollArea";
import { useProductLookup } from "@/hooks/use-lookup";
import { isSerialLine } from "@/lib/removals";
import type { RemovalLine } from "@/lib/types";

/**
 * The lines of a supplier return or a write-off. One table for both, because
 * `RemovalLine` is one shape shared by the two documents — they differ in
 * what confirming them means, not in what a line says.
 *
 * No money column: neither payload carries a figure. What a removal is worth
 * is the goods' book value, and the financial ledger is the only place that
 * holds it.
 */
export function RemovalLinesTable({
  lines,
  emptyMessage,
  onRemove,
  removeLabel,
  removing,
}: {
  lines: RemovalLine[];
  emptyMessage: string;
  /** Omitted once the document is no longer a draft. */
  onRemove?: (imei: string) => void;
  removeLabel?: string;
  removing?: boolean;
}) {
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

  return (
    <TableScrollArea>
      <Table verticalSpacing="sm" miw={560}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{tDoc("product")}</Table.Th>
            <Table.Th>IMEI</Table.Th>
            <Table.Th>{tDoc("quantity")}</Table.Th>
            {onRemove && <Table.Th />}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {lines.map((line) => (
            <Table.Tr key={line.id}>
              <Table.Td>{products.get(line.productId) ?? tCommon("none")}</Table.Td>
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
              <Table.Td>{line.quantity}</Table.Td>
              {onRemove && (
                <Table.Td>
                  <Group gap="2xs" justify="flex-end" wrap="nowrap">
                    {/* Unscan names the IMEI, so an accessory line has no
                        button — it is removed by re-scanning it down. */}
                    {isSerialLine(line) && line.imei !== null && (
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
          ))}
        </Table.Tbody>
      </Table>
    </TableScrollArea>
  );
}
