"use client";

import {
  Alert,
  Anchor,
  Button,
  Card,
  Group,
  Skeleton,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { useCan } from "@/components/MeProvider";
import { MoneyInput } from "@/components/MoneyInput";
import { useCurrentRates, useSetRate } from "@/hooks/use-exchange-rates";
import { Permission } from "@/lib/permissions";
import type { RateKind } from "@/lib/types";

/** A whole or fractional number of som per dollar. Empty means "unchanged". */
function isValidRate(value: string): boolean {
  return /^\d+(\.\d{1,4})?$/.test(value) && Number(value) > 0;
}

/**
 * The rate of the day, entered where the counter will actually see it.
 *
 * Nothing in the app converts with it (W9 B1). It is recorded so that a
 * sale priced in dollars and paid for in som can be read back later against
 * the figure the store was quoting at the time.
 */
export function RatesCard() {
  const t = useTranslations("rates");
  const can = useCan();
  const { data, isPending } = useCurrentRates();
  const save = useSetRate();

  // Null until someone types: the field shows the stored rate and follows
  // it, and a draft takes over only once it exists. That way a refetch
  // cannot overwrite what is being typed, and no effect has to seed it.
  const [saleDraft, setSaleDraft] = useState<string | null>(null);
  const [buybackDraft, setBuybackDraft] = useState<string | null>(null);

  if (!can(Permission.ExchangeRate.View)) return null;
  if (isPending) return <Skeleton height={140} radius="md" />;

  const manage = can(Permission.ExchangeRate.Manage);
  const stale = Boolean(data?.sale?.isStale || data?.buyback?.isStale);
  const quoted = data?.sale ?? data?.buyback ?? null;
  const storedSale = data?.sale?.somPerUsd ?? "";
  const storedBuyback = data?.buyback?.somPerUsd ?? "";
  const sale = saleDraft ?? storedSale;
  const buyback = buybackDraft ?? storedBuyback;

  const changed = sale !== storedSale || buyback !== storedBuyback;
  const malformed =
    (sale !== "" && !isValidRate(sale)) || (buyback !== "" && !isValidRate(buyback));
  // A rate that has not moved for days still has to be quoted for today,
  // or the month reads those days at an older figure. Same number, new row.
  const confirming = stale && !changed;

  const submit = async () => {
    const writes: { kind: RateKind; somPerUsd: string }[] = [];
    if (sale !== "" && (sale !== storedSale || data?.sale?.isStale)) {
      writes.push({ kind: "sale", somPerUsd: sale });
    }
    if (buyback !== "" && (buyback !== storedBuyback || data?.buyback?.isStale)) {
      writes.push({ kind: "buyback", somPerUsd: buyback });
    }
    for (const write of writes) {
      await save.mutateAsync(write);
    }
    // Hand the fields back to the server's answer.
    setSaleDraft(null);
    setBuybackDraft(null);
  };

  return (
    <Card withBorder radius="md" padding="lg">
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Stack gap="3xs">
            <Title order={4}>{t("title")}</Title>
            <Text size="sm" c="dimmed">
              {t("hint")}
            </Text>
          </Stack>
          <Anchor component={Link} href="/settings/rates" size="sm">
            {t("historyTitle")}
          </Anchor>
        </Group>

        {stale && quoted && (
          <Alert
            color="yellow"
            variant="light"
            icon={<IconAlertTriangle size={18} />}
          >
            {/* Already YYYY-MM-DD from the server, and parsing it into a
                Date would shift the day for a negative UTC offset. */}
            {t("stale", { date: quoted.effectiveOn })}
          </Alert>
        )}
        {!data?.sale && !data?.buyback && (
          <Alert color="blue" variant="light">
            {t("neverSet")}
          </Alert>
        )}

        <Group grow align="flex-start">
          <MoneyInput
            label={t("sale")}
            description={t("saleHint")}
            value={sale}
            onChange={setSaleDraft}
            currency="UZS"
            disabled={!manage}
            error={sale !== "" && !isValidRate(sale) ? t("malformed") : undefined}
          />
          <MoneyInput
            label={t("buyback")}
            description={t("buybackHint")}
            value={buyback}
            onChange={setBuybackDraft}
            currency="UZS"
            disabled={!manage}
            error={buyback !== "" && !isValidRate(buyback) ? t("malformed") : undefined}
          />
        </Group>

        <Text size="xs" c="dimmed">
          {t("example")}
        </Text>

        {manage && (
          <Group justify="flex-end">
            <Button
              onClick={submit}
              loading={save.isPending}
              disabled={(!changed && !confirming) || malformed}
            >
              {confirming ? t("confirmToday") : t("save")}
            </Button>
          </Group>
        )}
      </Stack>
    </Card>
  );
}