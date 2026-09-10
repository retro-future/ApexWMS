"use client";

import {
  Alert,
  Button,
  Card,
  Group,
  NumberInput,
  Stack,
  Text,
} from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { ProductSelect } from "@/components/ProductSelect";
import { useDocumentAction } from "@/hooks/use-document";
import { formatMoney } from "@/lib/money";
import { errorMessage } from "@/lib/notify";
import type { InvoiceScanResult, Product, SalesInvoice } from "@/lib/types";

/**
 * Add an accessory to a draft invoice without a scanner (FR-4.2).
 *
 * Picking the product from the catalogue does exactly what scanning its
 * barcode does: an accessory line is (product, quantity, catalog price). A
 * phone is not offered here, and the server refuses one anyway.
 */
export function AddAccessoryLine({
  invoice,
  onAdded,
}: {
  invoice: SalesInvoice;
  onAdded: (result: InvoiceScanResult) => void;
}) {
  const t = useTranslations("invoices.sell");
  const tCommon = useTranslations("common");

  const [product, setProduct] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState<number>(1);
  const [rejection, setRejection] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<string | null>(null);

  const add = useDocumentAction<
    InvoiceScanResult,
    { productId: string; quantity: number }
  >("invoices", invoice.id, { path: "/lines", invalidate: false });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!product) return;

    setRejection(null);
    try {
      const result = await add.mutateAsync({
        productId: product.id,
        quantity,
      });
      if (result) {
        onAdded(result);
        setAccepted(
          t("accepted", {
            price: formatMoney(result.resolvedPrice),
            count: result.lineCount,
          }),
        );
      }
      setProduct(null);
      setQuantity(1);
    } catch (error) {
      setAccepted(null);
      setRejection(errorMessage(error, tCommon("retry")));
    }
  }

  return (
    <Card withBorder radius="md" padding="lg">
      <form onSubmit={submit} noValidate>
        <Stack gap="md">
          <Text fw={500}>{t("addManualTitle")}</Text>
          <Text size="sm" c="dimmed">
            {t("addManualHint")}
          </Text>

          <Group gap="sm" align="flex-end" wrap="wrap">
            <ProductSelect
              value={product?.id ?? null}
              onChange={setProduct}
              label={t("addManualProduct")}
              placeholder={t("addManualProductPlaceholder")}
              trackingType="quantity"
            />
            <NumberInput
              label={t("addManualQuantity")}
              value={quantity}
              onChange={(value) =>
                setQuantity(typeof value === "number" ? value : 1)
              }
              min={1}
              max={999}
              allowDecimal={false}
              w={{ base: "100%", sm: 120 }}
            />
            <Button type="submit" loading={add.isPending} disabled={!product}>
              {t("addManualSubmit")}
            </Button>
          </Group>

          {rejection && (
            <Alert
              variant="light"
              color="red"
              icon={<IconAlertCircle size={18} />}
              role="alert"
            >
              {rejection}
            </Alert>
          )}

          {!rejection && accepted && (
            <Text size="sm" c="teal">
              {accepted}
            </Text>
          )}
        </Stack>
      </form>
    </Card>
  );
}
