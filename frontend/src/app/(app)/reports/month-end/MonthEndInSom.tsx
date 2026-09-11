"use client";

import { Card, Group, Stack, Table, Text, Title } from "@mantine/core";
import { useTranslations } from "next-intl";

import { TableScrollArea } from "@/components/TableScrollArea";
import { formatMoney } from "@/lib/money";
import type { MonthEndReport, SomFigures } from "@/lib/types";

/** What the profit is made of, in the order it adds up. */
const PARTS = [
  "margin",
  "rateGain",
  "instalmentIncome",
] as const satisfies readonly (keyof SomFigures)[];

/** The month's movement, for context under the answer. */
const MOVEMENT = [
  "openingInventory",
  "purchases",
  "revenue",
  "salesReturns",
  "costOfGoods",
  "closingInventory",
] as const satisfies readonly (keyof SomFigures)[];

/**
 * The same month in som: converted at each day's rate, plus the two gaps
 * between that conversion and the money that really changed hands.
 *
 * One figure is the answer and the rest are its working, so the layout says
 * which is which: an owner who reads only the top line has read the report
 * correctly. A block of its own rather than a column beside the others,
 * because in the tables above a som column means what crossed the counter.
 */
export function MonthEndInSom({ report }: { report: MonthEndReport }) {
  const t = useTranslations("reports");
  const som = report.som;
  if (som === null) {
    return (
      <Stack gap="3xs">
        <Title order={4}>{t("inSomTitle")}</Title>
        <Text size="sm" c="dimmed">
          {t("inSomNoRate")}
        </Text>
      </Stack>
    );
  }

  return (
    <>
      <Stack gap="3xs">
        <Title order={4}>{t("inSomTitle")}</Title>
        <Text size="sm" c="dimmed">
          {t("inSomBasis", {
            opening: som.openingRate,
            closing: som.closingRate,
          })}
        </Text>
        {som.beforeTheFirstQuote && (
          <Text size="sm" c="dimmed">
            {t("inSomBeforeTheLog")}
          </Text>
        )}
      </Stack>

      <Card withBorder radius="md" padding="lg">
        <Stack gap="sm">
          <Group justify="space-between" align="flex-end" wrap="wrap">
            <Stack gap={0}>
              <Text size="sm" c="dimmed">
                {t("profit")}
              </Text>
              <Text fz="xl" fw={700}>
                {formatMoney(som.profit)}
              </Text>
            </Stack>
            <Text size="sm" c="dimmed" maw={320} ta="right">
              {t("profitHint")}
            </Text>
          </Group>
          <Table verticalSpacing="xs">
            <Table.Tbody>
              {PARTS.map((row) => (
                <Table.Tr key={row}>
                  <Table.Td>
                    <Text size="sm">{t(row)}</Text>
                  </Table.Td>
                  <Table.Td ta="right">
                    <Text size="sm">{formatMoney(som[row])}</Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      </Card>

      <TableScrollArea>
        <Table highlightOnHover verticalSpacing="sm" miw={360}>
          <Table.Tbody>
            {MOVEMENT.map((row) => (
              <Table.Tr key={row}>
                <Table.Td>
                  <Text size="sm" fw={500}>
                    {t(row)}
                  </Text>
                </Table.Td>
                <Table.Td ta="right">
                  <Text size="sm">{formatMoney(som[row])}</Text>
                </Table.Td>
              </Table.Tr>
            ))}
            <Table.Tr>
              <Table.Td>
                <Text size="sm" fw={500}>
                  {t("marginPercent")}
                </Text>
              </Table.Td>
              <Table.Td ta="right">
                <Text size="sm" c={som.marginPercent === null ? "dimmed" : undefined}>
                  {som.marginPercent === null ? "—" : `${som.marginPercent}%`}
                </Text>
              </Table.Td>
            </Table.Tr>
          </Table.Tbody>
        </Table>
      </TableScrollArea>
    </>
  );
}
