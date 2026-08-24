"use client";

import { ActionIcon, Badge, Group, Table, Tabs, Text } from "@mantine/core";
import { IconTrash } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { TableScrollArea } from "@/components/TableScrollArea";
import { useProductLookup } from "@/hooks/use-lookup";
import { unitsByOutcome } from "@/lib/stock-counts";
import type { CountOutcome, StockCount, StockCountUnit } from "@/lib/types";

const OUTCOME_COLOR: Record<CountOutcome, string> = {
  matched: "teal",
  missing: "orange",
  unexpected: "grape",
};

/**
 * FR-6.3's three lists: matched, missing, and unexpected.
 *
 * There is no report endpoint to call — the count payload *is* the report.
 * Each row carries the outcome it computed from two booleans, so the three
 * lists are a split rather than a fetch.
 */
export function DiscrepancyReport({
  count,
  onUnscan,
  unscanning,
}: {
  count: StockCount;
  /** Omitted once the count is closed: nothing can be scanned or unscanned then. */
  onUnscan?: (unit: StockCountUnit) => void;
  unscanning?: boolean;
}) {
  const t = useTranslations("stockCounts");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const products = useProductLookup();
  const [tab, setTab] = useState<string | null>("missing");

  const lists = unitsByOutcome(count);

  function panel(outcome: CountOutcome, units: StockCountUnit[]) {
    if (units.length === 0) {
      return (
        <Text size="sm" c="dimmed" pt="md">
          {t(`empty.${outcome}`)}
        </Text>
      );
    }

    return (
      <TableScrollArea>
        <Table verticalSpacing="sm" miw={560}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>IMEI</Table.Th>
              <Table.Th>{tDoc("product")}</Table.Th>
              {outcome === "unexpected" && <Table.Th>{t("origin")}</Table.Th>}
              {onUnscan && <Table.Th />}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {units.map((unit) => (
              <Table.Tr key={unit.id}>
                <Table.Td>
                  <Text size="sm" ff="monospace">
                    {unit.imei}
                  </Text>
                </Table.Td>
                <Table.Td>
                  {unit.productId === null
                    ? tCommon("none")
                    : (products.get(unit.productId) ?? tCommon("none"))}
                </Table.Td>
                {outcome === "unexpected" && (
                  <Table.Td>
                    <Badge
                      size="sm"
                      variant="light"
                      color={unit.isSurprise ? "grape" : "blue"}
                    >
                      {/* A surprise has no row at all; the other kind was
                          simply on a different shelf, and moves goods
                          without moving money. */}
                      {unit.isSurprise ? t("surprise") : t("elsewhere")}
                    </Badge>
                  </Table.Td>
                )}
                {onUnscan && (
                  <Table.Td>
                    <Group gap="2xs" justify="flex-end" wrap="nowrap">
                      {unit.scanned && (
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          aria-label={t("scan.unscan")}
                          loading={unscanning}
                          onClick={() => onUnscan(unit)}
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

  return (
    <Tabs value={tab} onChange={setTab}>
      <Tabs.List>
        <Tabs.Tab
          value="missing"
          rightSection={
            <Badge size="xs" variant="light" color={OUTCOME_COLOR.missing} circle>
              {count.missingCount}
            </Badge>
          }
        >
          {tDoc("countOutcome.missing")}
        </Tabs.Tab>
        <Tabs.Tab
          value="unexpected"
          rightSection={
            <Badge size="xs" variant="light" color={OUTCOME_COLOR.unexpected} circle>
              {count.unexpectedCount}
            </Badge>
          }
        >
          {tDoc("countOutcome.unexpected")}
        </Tabs.Tab>
        <Tabs.Tab
          value="matched"
          rightSection={
            <Badge size="xs" variant="light" color={OUTCOME_COLOR.matched} circle>
              {count.matchedCount}
            </Badge>
          }
        >
          {tDoc("countOutcome.matched")}
        </Tabs.Tab>
      </Tabs.List>

      <Tabs.Panel value="missing">{panel("missing", lists.missing)}</Tabs.Panel>
      <Tabs.Panel value="unexpected">
        {panel("unexpected", lists.unexpected)}
      </Tabs.Panel>
      <Tabs.Panel value="matched">{panel("matched", lists.matched)}</Tabs.Panel>
    </Tabs>
  );
}
