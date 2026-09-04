"use client";

import {
  Alert,
  Card,
  Center,
  Group,
  Loader,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Subtotals } from "@/components/Subtotals";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useLocationLookup } from "@/hooks/use-lookup";
import { apiGet, queryString } from "@/lib/api";
import type { SalesFigures, SalesSummary } from "@/lib/types";

/**
 * FR-9.3: what selling earned, by location, over a date range.
 *
 * Unpaged, because the store total is only meaningful with every location in
 * hand. Every money figure is one subtotal per currency: `costOfGoods` and
 * `returns` keep §4.6's sign and are negative, and `margin` is their plain
 * sum, so nothing on this screen flips a sign or adds so'm to dollars.
 */
export function SalesSummaryReport() {
  const t = useTranslations("reports");
  const tCommon = useTranslations("common");

  const locations = useLocationLookup();

  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [locationId, setLocationId] = useState<string | null>(null);

  const params = {
    fromDate: from ? new Date(from).toISOString() : undefined,
    // Through the end of the chosen day, not its first instant.
    toDate: to ? new Date(`${to}T23:59:59.999Z`).toISOString() : undefined,
    locationId: locationId ?? undefined,
  };

  const query = useQuery<SalesSummary>({
    queryKey: ["reports/sales-summary", params],
    queryFn: () =>
      apiGet<SalesSummary>(`/reports/sales-summary${queryString(params)}`),
  });

  const summary = query.data;

  return (
    <Stack gap="lg">
      <Stack gap="3xs">
        <Title order={2}>{t("salesSummaryTitle")}</Title>
        <Text size="sm" c="dimmed">
          {t("salesSummarySubtitle")}
        </Text>
      </Stack>

      <Group gap="sm" wrap="wrap" align="flex-end">
        <TextInput
          type="date"
          label={t("from")}
          value={from}
          onChange={(event) => setFrom(event.currentTarget.value)}
          w={{ base: "100%", sm: 160 }}
        />
        <TextInput
          type="date"
          label={t("to")}
          value={to}
          onChange={(event) => setTo(event.currentTarget.value)}
          w={{ base: "100%", sm: 160 }}
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
      </Group>

      {query.error ? (
        <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
          {query.error instanceof Error ? query.error.message : tCommon("retry")}
        </Alert>
      ) : query.isLoading || !summary ? (
        <Center p="xl">
          <Loader size="sm" />
        </Center>
      ) : (
        <>
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 5 }}>
            <Card withBorder radius="md" padding="lg">
              <Stack gap="3xs">
                <Text size="sm" c="dimmed">
                  {t("unitsSold")}
                </Text>
                <Text fz="2xl" fw={700}>
                  {summary.total.unitsSold}
                </Text>
              </Stack>
            </Card>
            <FigureCard label={t("revenue")} subtotals={summary.total.revenue} />
            <FigureCard
              label={t("salesReturns")}
              subtotals={summary.total.returns}
            />
            <FigureCard
              label={t("costOfGoods")}
              subtotals={summary.total.costOfGoods}
            />
            <FigureCard label={t("margin")} subtotals={summary.total.margin} />
          </SimpleGrid>

          <TableScrollArea>
            <Table highlightOnHover verticalSpacing="sm" miw={640}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t("filterLocation")}</Table.Th>
                  <Table.Th>{t("unitsSold")}</Table.Th>
                  <Table.Th>{t("revenue")}</Table.Th>
                  <Table.Th>{t("salesReturns")}</Table.Th>
                  <Table.Th>{t("costOfGoods")}</Table.Th>
                  <Table.Th>{t("margin")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {summary.locations.map((entry) => (
                  <Table.Tr key={entry.locationId ?? "unattributed"}>
                    <Table.Td>
                      <Text size="sm" fw={500}>
                        {entry.locationName ?? t("unattributed")}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{entry.figures.unitsSold}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Subtotals subtotals={entry.figures.revenue} />
                    </Table.Td>
                    <Table.Td>
                      <Subtotals subtotals={entry.figures.returns} />
                    </Table.Td>
                    <Table.Td>
                      <Subtotals subtotals={entry.figures.costOfGoods} />
                    </Table.Td>
                    <Table.Td>
                      <Subtotals subtotals={entry.figures.margin} fw={600} />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>

            {summary.locations.length === 0 && (
              <Center p="xl">
                <Text fw={500}>{t("noSales")}</Text>
              </Center>
            )}
          </TableScrollArea>

          <Text size="sm" c="dimmed">
            {t("costOfGoodsHint")}
          </Text>
        </>
      )}
    </Stack>
  );
}

function FigureCard({
  label,
  subtotals,
}: {
  label: string;
  subtotals: SalesFigures["revenue"];
}) {
  return (
    <Card withBorder radius="md" padding="lg">
      <Stack gap="3xs">
        <Text size="sm" c="dimmed">
          {label}
        </Text>
        <Subtotals subtotals={subtotals} size="lg" fw={700} />
      </Stack>
    </Card>
  );
}
