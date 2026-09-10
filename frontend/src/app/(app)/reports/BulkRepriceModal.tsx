"use client";

import { Center, Loader, Stack, Table, Text, Textarea } from "@mantine/core";
import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { MoneyInput } from "@/components/MoneyInput";
import { apiGet, apiSend } from "@/lib/api";
import { isValidPriceInput, moneyToInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import type { DeviceUnit } from "@/lib/types";

/**
 * FR-2.21: price several handsets off one report in a single call.
 *
 * Each unit's new price is stated — there is no "cut everything by 10%",
 * because a percentage across handsets in different conditions is the
 * automated valuation §1.3 rejects. The reason is shared: this is one
 * decision applied to several phones, not several decisions.
 *
 * The units are fetched here rather than taken from the report row, because
 * a price cannot be typed without knowing which currency it is in and
 * neither worklist carries one.
 */
export function BulkRepriceModal({
  deviceUnitIds,
  onClose,
  onDone,
}: {
  deviceUnitIds: string[];
  onClose: () => void;
  onDone: () => void;
}) {
  const t = useTranslations("reports");
  const tUnits = useTranslations("deviceUnits");
  const tCommon = useTranslations("common");
  const tDoc = useTranslations("documents");
  const queryClient = useQueryClient();

  const units = useQueries({
    queries: deviceUnitIds.map((id) => ({
      queryKey: ["device-units", "item", id],
      queryFn: () => apiGet<DeviceUnit>(`/device-units/${id}`),
    })),
  });

  const [prices, setPrices] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loaded = units.every((unit) => unit.data);
  const rows = units.map((unit) => unit.data).filter(Boolean) as DeviceUnit[];

  const reprice = useMutation({
    mutationFn: (payload: {
      prices: { deviceUnitId: string; askingPrice: string }[];
      reason: string | null;
    }) => apiSend<number>("POST", "/device-units/price", payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["device-units"] });
      queryClient.invalidateQueries({ queryKey: ["reports/needs-pricing"] });
      queryClient.invalidateQueries({ queryKey: ["reports/ageing"] });
    },
  });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const stated = rows.filter((unit) => (prices[unit.id] ?? "").trim());
    if (stated.length === 0) {
      setError(t("bulkRepriceEmpty"));
      return;
    }
    const bad = stated.find(
      (unit) => !isValidPriceInput(prices[unit.id], unit.currency),
    );
    if (bad) {
      setError(bad.currency === "USD" ? tDoc("priceHintUsd") : tDoc("priceHintUzs"));
      return;
    }

    try {
      await reprice.mutateAsync({
        prices: stated.map((unit) => ({
          deviceUnitId: unit.id,
          askingPrice: prices[unit.id].trim(),
        })),
        reason: reason.trim() || null,
      });
      notifySuccess(t("bulkRepriced", { count: stated.length }));
      onDone();
      onClose();
    } catch (thrown) {
      setError(errorMessage(thrown, tCommon("retry")));
    }
  }

  return (
    <FormModal
      opened
      onClose={onClose}
      title={t("bulkRepriceTitle")}
      onSubmit={submit}
      busy={reprice.isPending}
      error={error}
      submitLabel={tCommon("save")}
    >
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          {t("bulkRepriceHint")}
        </Text>

        {!loaded ? (
          <Center p="md">
            <Loader size="sm" />
          </Center>
        ) : (
          <Table verticalSpacing="xs">
            <Table.Tbody>
              {rows.map((unit) => (
                <Table.Tr key={unit.id}>
                  <Table.Td>
                    <Text size="sm">{unit.productName}</Text>
                    <Text size="xs" c="dimmed" ff="monospace">
                      {unit.imei}
                    </Text>
                  </Table.Td>
                  <Table.Td w={160}>
                    <MoneyInput
                      aria-label={`${tUnits("newPrice")} ${unit.imei}`}
                      value={prices[unit.id] ?? ""}
                      placeholder={moneyToInput(unit.askingPrice)}
                      onChange={(value) =>
                        setPrices((current) => ({ ...current, [unit.id]: value }))
                      }
                      currency={unit.currency}
                    />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}

        <Textarea
          label={tDoc("reason")}
          description={t("bulkReasonHint")}
          value={reason}
          onChange={(event) => setReason(event.currentTarget.value)}
          autosize
          minRows={2}
        />
      </Stack>
    </FormModal>
  );
}
