"use client";

import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ConditionModal } from "@/app/(app)/device-units/ConditionModal";
import { RepriceModal } from "@/app/(app)/device-units/RepriceModal";
import { SellUnitModal } from "@/app/(app)/device-units/SellUnitModal";
import { DetailError, DetailLoading } from "@/components/DetailStates";
import { DeviceTraceTimeline } from "@/components/DeviceTraceTimeline";
import { useCan } from "@/components/MeProvider";
import { useLocationLookup } from "@/hooks/use-lookup";
import { useResourceItem } from "@/hooks/use-resource";
import { Permission } from "@/lib/permissions";
import type { DeviceUnit } from "@/lib/types";

/** A handset that has left stock is settled: no repricing, no re-grading. */
const ON_HAND = new Set(["in_stock", "reserved"]);

export default function DeviceUnitPage() {
  const t = useTranslations("deviceUnits");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const tSell = useTranslations("invoices.sell");
  const tReports = useTranslations("reports");
  const { id } = useParams<{ id: string }>();
  const can = useCan();

  const query = useResourceItem<DeviceUnit>("device-units", id);
  const locations = useLocationLookup();

  const canPrice = can(Permission.Pricing.Set);

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

      {/* FR-9.2: the whole life of the handset, price log included. Open
          to anyone who may see the unit - the events carry prices, never
          costs. */}
      <Card withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Text fw={500}>{tReports("traceHeading")}</Text>
          <DeviceTraceTimeline deviceUnitId={id} />
        </Stack>
      </Card>

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
