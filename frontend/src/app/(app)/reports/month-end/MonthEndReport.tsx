"use client";

import {
  Alert,
  Center,
  Group,
  Loader,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconAlertCircle, IconCircleCheck } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { MonthEndDebtAndFinancing } from "@/app/(app)/reports/month-end/MonthEndDebtAndFinancing";
import { MonthEndStockAndSales } from "@/app/(app)/reports/month-end/MonthEndStockAndSales";
import { OpenPdfButton } from "@/components/OpenPdfButton";
import { Subtotals } from "@/components/Subtotals";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useLocationLookup } from "@/hooks/use-lookup";
import { apiGet, queryString } from "@/lib/api";
import {
  formatPeriod,
  fromMonthInput,
  lastCompletedMonth,
  toMonthInput,
} from "@/lib/month-end";
import type { MonthEndReport } from "@/lib/types";

/**
 * FR-10.4: how the store did in one month, at one location or across all.
 *
 * Opens on the month that has finished, because that is what a close is for.
 * The figures split into two tables (`MonthEndStockAndSales`): a stock-value
 * bridge from opening to closing, and a plain sales/margin view. A dollar
 * figure and a som figure never share a cell in either.
 */
export function MonthEndReportScreen() {
  const t = useTranslations("reports");
  const tCommon = useTranslations("common");

  const locations = useLocationLookup();

  const [month, setMonth] = useState(() =>
    toMonthInput(lastCompletedMonth(new Date())),
  );
  const [locationId, setLocationId] = useState<string | null>(null);

  const period = fromMonthInput(month);
  const params = {
    year: period?.year,
    month: period?.month,
    locationId: locationId ?? undefined,
  };

  const query = useQuery<MonthEndReport>({
    queryKey: ["reports/month-end", params],
    queryFn: () =>
      apiGet<MonthEndReport>(`/reports/month-end${queryString(params)}`),
    enabled: period !== null,
  });

  const report = query.data;

  return (
    <Stack gap="lg">
      <Stack gap="3xs">
        <Title order={2}>{t("monthEndTitle")}</Title>
        <Text size="sm" c="dimmed">
          {t("monthEndSubtitle")}
        </Text>
      </Stack>

      <Group gap="sm" wrap="wrap" align="flex-end">
        <TextInput
          type="month"
          label={t("month")}
          value={month}
          onChange={(event) => setMonth(event.currentTarget.value)}
          w={{ base: "100%", sm: 180 }}
        />
        <Select
          value={locationId}
          onChange={setLocationId}
          placeholder={t("filterLocation")}
          clearable
          searchable
          w={{ base: "100%", sm: 200 }}
          data={locations.all.map((location) => ({
            value: location.id,
            label: location.name,
          }))}
        />
        {period && (
          <OpenPdfButton
            href={`/api/backend/reports/month-end/pdf${queryString(params)}`}
          />
        )}
      </Group>

      {period === null ? (
        <Center p="xl">
          <Text fw={500}>{t("chooseMonth")}</Text>
        </Center>
      ) : query.error ? (
        <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
          {query.error instanceof Error ? query.error.message : tCommon("retry")}
        </Alert>
      ) : query.isLoading || !report ? (
        <Center p="xl">
          <Loader size="sm" />
        </Center>
      ) : (
        <>
          <Text size="sm" c="dimmed">
            {formatPeriod(report.period)}
          </Text>

          <Reconciliation report={report} />

          <MonthEndStockAndSales report={report} />

          <Stack gap="3xs">
            <Title order={4}>{t("closingByLocation")}</Title>
            <Text size="sm" c="dimmed">
              {t("closingByLocationHint")}
            </Text>
          </Stack>

          <TableScrollArea>
            <Table highlightOnHover verticalSpacing="sm" miw={480}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t("filterLocation")}</Table.Th>
                  <Table.Th>{t("quantity")}</Table.Th>
                  <Table.Th>{t("closingInventory")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {report.closingByLocation.map((entry) => (
                  <Table.Tr key={entry.locationId}>
                    <Table.Td>
                      <Text size="sm" fw={500}>
                        {entry.locationName ?? t("unattributed")}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{entry.quantity}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Subtotals subtotals={entry.value} />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>

            {report.closingByLocation.length === 0 && (
              <Center p="xl">
                <Text fw={500}>{t("noClosingStock")}</Text>
              </Center>
            )}
          </TableScrollArea>

          <MonthEndDebtAndFinancing report={report} />
        </>
      )}
    </Stack>
  );
}

/**
 * FR-10.7 and FR-10.7b, said either way. A mismatch is surfaced beside the
 * figures rather than instead of them: the owner still gets the month, and
 * nothing here rewrites one side to match the other.
 */
function Reconciliation({ report }: { report: MonthEndReport }) {
  const t = useTranslations("reports");

  if (report.reconciles) {
    return (
      <Alert
        variant="light"
        color="green"
        icon={<IconCircleCheck size={18} />}
        title={t("reconciles")}
      >
        {t("reconcilesHint")}
      </Alert>
    );
  }

  return (
    <Alert
      variant="light"
      color="red"
      icon={<IconAlertCircle size={18} />}
      title={t("doesNotReconcile")}
    >
      <Stack gap="3xs">
        <Text size="sm">{t("doesNotReconcileHint")}</Text>
        {report.discrepancies.map((found) => (
          <Text key={found.subject} size="sm">
            {t("discrepancy", {
              subject: found.subject,
              expected: found.expected,
              found: found.found,
            })}
          </Text>
        ))}
      </Stack>
    </Alert>
  );
}
