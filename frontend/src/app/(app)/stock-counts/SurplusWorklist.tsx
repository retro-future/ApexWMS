"use client";

import { Alert, Button, Card, Group, Stack, Table, Text } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { useCan } from "@/components/MeProvider";
import { MoneyInput } from "@/components/MoneyInput";
import { ProductSelect } from "@/components/ProductSelect";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useDocumentAction } from "@/hooks/use-document";
import { useProductLookup } from "@/hooks/use-lookup";
import { isValidPriceInput } from "@/lib/money";
import { errorMessage } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { CountScanResult, Product, StockCount, StockCountUnit } from "@/lib/types";

/**
 * The handsets a confirm cannot value yet (FR-6.4b).
 *
 * A surplus with nothing to value it is refused rather than booked at zero:
 * `verify-financials` recomputes inventory value by summing on-hand cost, so
 * a zero would either drift or dilute every later weighted average. The
 * server states this by naming every offending IMEI in one message, because
 * the person fixing it is standing at a shelf and a refusal that reveals its
 * gaps one at a time turns that into ten round trips.
 *
 * This panel is the same list, computed before the button is pressed. Stating
 * a cost re-scans the IMEI: a repeat beep on a count changes nothing about
 * what was found, and may carry the product and cost the first one lacked.
 *
 * It renders only under `Cost.View`, because without that permission the
 * server omits the cost from every row and an unvalued handset is
 * indistinguishable from one somebody already priced. Editing takes
 * `Pricing.Set` on top: a Storekeeper sees the list and cannot act on it,
 * which is the point — they can fetch someone who can.
 */
export function SurplusWorklist({
  count,
  units,
  onFixed,
}: {
  count: StockCount;
  units: StockCountUnit[];
  onFixed: (result: CountScanResult) => void;
}) {
  const t = useTranslations("stockCounts.surplus");
  const tCommon = useTranslations("common");
  const tDoc = useTranslations("documents");
  const can = useCan();
  const products = useProductLookup();

  const canView = can(Permission.Cost.View);
  const canPrice = can(Permission.Pricing.Set);

  const [drafts, setDrafts] = useState<
    Record<string, { product: Product | null; cost: string }>
  >({});
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const scan = useDocumentAction<
    CountScanResult,
    { code: string; productId: string; acquisitionCost: string }
  >("stock-counts", count.id, { path: "/scan", invalidate: false });

  if (units.length === 0) return null;

  // Without Cost.View there is no cost field to read, so the list cannot be
  // computed honestly. Say how many there are and who can fix them.
  if (!canView) {
    return (
      <Alert variant="light" color="yellow" icon={<IconAlertCircle size={18} />}>
        {t("noCostView", { count: units.length })}
      </Alert>
    );
  }

  function draftFor(unit: StockCountUnit) {
    return (
      drafts[unit.id] ?? {
        product: null,
        cost: "",
      }
    );
  }

  /**
   * A row can be unvalued for either of two reasons: the store has no idea
   * what the handset is, or it knows the model and nobody stated a cost. In
   * the second case the product is already settled and only the money is
   * missing.
   */
  function productFor(unit: StockCountUnit): Product | null {
    if (unit.productId !== null) {
      return products.all.find((product) => product.id === unit.productId) ?? null;
    }
    return draftFor(unit).product;
  }

  function isRowValid(unit: StockCountUnit): boolean {
    const product = productFor(unit);
    const { cost } = draftFor(unit);
    // A cost is denominated by the model it belongs to (§4.5 rule 3), so the
    // server refuses one stated without a product. Require both together.
    if (!product || !cost.trim()) return false;
    return isValidPriceInput(cost, product.currency);
  }

  async function save(unit: StockCountUnit) {
    const product = productFor(unit);
    if (!product || !isRowValid(unit)) return;

    setError(null);
    setPending(unit.id);
    try {
      const result = await scan.mutateAsync({
        code: unit.imei,
        productId: product.id,
        acquisitionCost: draftFor(unit).cost.trim(),
      });
      if (result) onFixed(result);
      setDrafts((current) => {
        const next = { ...current };
        delete next[unit.id];
        return next;
      });
    } catch (caught) {
      setError(errorMessage(caught, tCommon("retry")));
    } finally {
      setPending(null);
    }
  }

  return (
    <Card withBorder radius="md" padding="lg">
      <Stack gap="md">
        <Group justify="space-between" align="flex-end" wrap="wrap">
          <Stack gap="3xs">
            <Text fw={500}>{t("title")}</Text>
            <Text size="sm" c="dimmed">
              {t("hint")}
            </Text>
          </Stack>
          <Text size="sm" fw={600} c="orange">
            {units.length}
          </Text>
        </Group>

        {error && (
          <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
            {error}
          </Alert>
        )}

        {!canPrice && (
          <Alert variant="light" color="yellow" icon={<IconAlertCircle size={18} />}>
            {t("readOnly")}
          </Alert>
        )}

        <TableScrollArea>
          <Table verticalSpacing="sm" miw={720}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>IMEI</Table.Th>
                <Table.Th>{tDoc("product")}</Table.Th>
                <Table.Th w={200}>{t("cost")}</Table.Th>
                {canPrice && <Table.Th w={100} />}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {units.map((unit) => {
                const draft = draftFor(unit);
                return (
                  <Table.Tr key={unit.id}>
                    <Table.Td>
                      <Text size="sm" ff="monospace">
                        {unit.imei}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      {/* A handset the store does know, that simply has no
                          cost, keeps the product it already names. */}
                      {unit.productId !== null ? (
                        <Text size="sm">
                          {products.get(unit.productId) ?? tCommon("none")}
                        </Text>
                      ) : canPrice ? (
                        <ProductSelect
                          value={draft.product?.id ?? null}
                          onChange={(product) =>
                            setDrafts((current) => ({
                              ...current,
                              // The cost was typed in the old currency.
                              [unit.id]: { product, cost: "" },
                            }))
                          }
                          placeholder={tDoc("product")}
                        />
                      ) : (
                        <Text size="sm" c="dimmed">
                          {tCommon("none")}
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      {canPrice ? (
                        <MoneyInput
                          value={draft.cost}
                          onChange={(cost) =>
                            setDrafts((current) => ({
                              ...current,
                              [unit.id]: { ...draftFor(unit), cost },
                            }))
                          }
                          currency={productFor(unit)?.currency}
                          // Only a row with no product identity at all is
                          // closed for typing. One whose model is known is
                          // open while the catalog list is still loading —
                          // Save stays disabled until its currency arrives,
                          // since a figure cannot be checked without one.
                          disabled={unit.productId === null && draft.product === null}
                          aria-label={t("costFor", { imei: unit.imei })}
                        />
                      ) : (
                        <Text size="sm" c="dimmed">
                          {tCommon("none")}
                        </Text>
                      )}
                    </Table.Td>
                    {canPrice && (
                      <Table.Td>
                        <Button
                          size="compact-sm"
                          variant="light"
                          disabled={!isRowValid(unit)}
                          loading={pending === unit.id}
                          onClick={() => save(unit)}
                        >
                          {tCommon("save")}
                        </Button>
                      </Table.Td>
                    )}
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </TableScrollArea>
      </Stack>
    </Card>
  );
}
