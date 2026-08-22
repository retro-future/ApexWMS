"use client";

import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ConditionModal } from "@/app/(app)/device-units/ConditionModal";
import { RepriceModal } from "@/app/(app)/device-units/RepriceModal";
import { SellUnitModal } from "@/app/(app)/device-units/SellUnitModal";
import { DetailError, DetailLoading } from "@/components/DetailStates";
import { useCan } from "@/components/MeProvider";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useDateFormat } from "@/hooks/use-date-format";
import { useLocationLookup } from "@/hooks/use-lookup";
import { useResourceItem } from "@/hooks/use-resource";
import { apiGet } from "@/lib/api";
import { Permission } from "@/lib/permissions";
import type { DeviceUnit, PriceChange } from "@/lib/types";

/** A handset that has left stock is settled: no repricing, no re-grading. */
const ON_HAND = new Set(["in_stock", "reserved"]);

export default function DeviceUnitPage() {
  const t = useTranslations("deviceUnits");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const tSell = useTranslations("invoices.sell");
  const { formatDateTime } = useDateFormat();
  const { id } = useParams<{ id: string }>();
  const can = useCan();

  const query = useResourceItem<DeviceUnit>("device-units", id);
  const locations = useLocationLookup();

  const canPrice = can(Permission.Pricing.Set);
  // Keyed under the unit so a reprice invalidates the log along with it.
  const history = useQuery<PriceChange[]>({
    queryKey: ["device-units", "item", id, "price-history"],
    queryFn: () => apiGet<PriceChange[]>(`/device-units/${id}/price-history`),
    enabled: canPrice,
  });

  const [repricing, setRepricing] = useState(false);
  const [regrading, setRegrading] = useState(false);
  const [selling, setSelling] = useState(false);

  if (query.isLoading) return <DetailLoading />;

  const unit = query.data;
  if (query.isError || !unit) {
    return (
      <DetailError
        message={query.error instanceof Error ? query.error.message : t("notFound")}
      />
    );
  }

  const onHand = ON_HAND.has(unit.status);

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <Stack gap="2xs">
          <Group gap="sm">
            <Title order={2} ff="monospace">
              {unit.imei}
            </Title>
            <Badge size="sm" variant="light" color={onHand ? "teal" : "gray"}>
              {tDoc(`deviceStatus.${unit.status}`)}
            </Badge>
            <Badge size="sm" variant="light">
              {tDoc(`condition.${unit.condition}`)}
            </Badge>
          </Group>
          <Text size="sm" c="dimmed">
            <Link href={`/products/${unit.productId}`}>{unit.productName}</Link>
            {" · "}
            {unit.sku}
            {unit.locationId && (
              <>
                {" · "}
                {locations.get(unit.locationId) ?? tCommon("none")}
              </>
            )}
          </Text>
        </Stack>

        <Group gap="sm">
          {unit.status === "in_stock" && can(Permission.Sales.Manage) && (
            <Button onClick={() => setSelling(true)}>{tSell("sellThis")}</Button>
          )}
          {canPrice && onHand && (
            <>
              <Button variant="light" onClick={() => setRepricing(true)}>
                {t("reprice")}
              </Button>
              <Button variant="light" onClick={() => setRegrading(true)}>
                {t("changeCondition")}
              </Button>
            </>
          )}
        </Group>
      </Group>

      {/* FR-2.14: the rule refused, so the screen says so rather than
          showing zero or the catalog price of a used handset. */}
      {unit.resolvedPrice === null && (
        <Alert variant="light" color="yellow" icon={<IconAlertCircle size={18} />}>
          <Text fw={500}>{t("notPriced")}</Text>
          <Text size="sm">{t("notPricedHint")}</Text>
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        <Figure
          label={t("resolvedPrice")}
          value={
            unit.resolvedPrice === null
              ? t("notPriced")
              : `${unit.resolvedPrice} ${unit.currency}`
          }
        />
        <Figure
          label={t("askingPrice")}
          value={
            unit.askingPrice === null
              ? tCommon("none")
              : `${unit.askingPrice} ${unit.currency}`
          }
        />
        {/* Absent without Cost.View — the payload never carried it (FR-1.7). */}
        {unit.acquisitionCost !== undefined && unit.acquisitionCost !== null && (
          <Figure
            label={t("acquisitionCost")}
            value={`${unit.acquisitionCost} ${unit.currency}`}
          />
        )}
        {unit.cashPaid && (
          <Figure
            label={t("cashPaid")}
            value={unit.cashPaid}
            hint={t("cashPaidHint")}
          />
        )}
      </SimpleGrid>

      {(unit.imei2 || unit.serialNumber) && (
        <Card withBorder radius="md" padding="lg">
          <Group gap="xl">
            {unit.imei2 && (
              <Figure label={t("imei2")} value={unit.imei2} mono />
            )}
            {unit.serialNumber && (
              <Figure label={t("serialNumber")} value={unit.serialNumber} mono />
            )}
          </Group>
        </Card>
      )}

      {canPrice && (
        <Card withBorder radius="md" padding="lg">
          <Stack gap="md">
            <Text fw={500}>{t("priceHistory")}</Text>
            {history.isLoading ? (
              <Center p="md">
                <Loader size="sm" />
              </Center>
            ) : (history.data ?? []).length === 0 ? (
              <Text size="sm" c="dimmed">
                {t("priceHistoryEmpty")}
              </Text>
            ) : (
              <TableScrollArea>
                <Table verticalSpacing="sm" miw={480}>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{tDoc("created")}</Table.Th>
                      <Table.Th>{t("askingPrice")}</Table.Th>
                      <Table.Th>{tDoc("reason")}</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {(history.data ?? []).map((change) => (
                      <Table.Tr key={change.id}>
                        <Table.Td>{formatDateTime(change.occurredAt)}</Table.Td>
                        <Table.Td>
                          {change.oldPrice === null
                            ? t("priceFirst", {
                                price: `${change.newPrice} ${change.currency}`,
                              })
                            : t("priceChanged", {
                                oldPrice: change.oldPrice,
                                newPrice: `${change.newPrice} ${change.currency}`,
                              })}
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm" c="dimmed">
                            {change.reason ?? tCommon("none")}
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </TableScrollArea>
            )}
          </Stack>
        </Card>
      )}

      {repricing && (
        <RepriceModal unit={unit} onClose={() => setRepricing(false)} />
      )}
      {regrading && (
        <ConditionModal unit={unit} onClose={() => setRegrading(false)} />
      )}
      {selling && <SellUnitModal unit={unit} onClose={() => setSelling(false)} />}
    </Stack>
  );
}

function Figure({
  label,
  value,
  hint,
  mono,
}: {
  label: string;
  value: string;
  hint?: string;
  mono?: boolean;
}) {
  return (
    <Stack gap="3xs">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text fw={600} ff={mono ? "monospace" : undefined}>
        {value}
      </Text>
      {hint && (
        <Text size="xs" c="dimmed">
          {hint}
        </Text>
      )}
    </Stack>
  );
}
