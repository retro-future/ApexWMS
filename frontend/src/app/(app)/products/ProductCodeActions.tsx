"use client";

import { Button, Card, Group, Stack, Text, Title } from "@mantine/core";
import { IconBarcode, IconTag } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useCan } from "@/components/MeProvider";
import { apiSend } from "@/lib/api";
import { errorMessage, notifyError, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { Product } from "@/lib/types";

const LABEL_BASE = "/api/backend/products";

export function ProductCodeActions({ product }: { product: Product }) {
  const t = useTranslations("products");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const can = useCan();

  const [generating, setGenerating] = useState(false);

  const canManage = can(Permission.Catalog.Manage);
  const needsBarcode =
    product.trackingType === "quantity" && product.barcode === null;

  async function generateBarcode() {
    setGenerating(true);
    try {
      await apiSend("POST", `/products/${product.id}/barcode`);
      notifySuccess(tCommon("updated"));
      router.refresh();
    } catch (err) {
      notifyError(errorMessage(err, tCommon("retry")));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <Card withBorder radius="md" padding="lg" maw={720}>
      <Stack gap="md">
        <Stack gap="3xs">
          <Title order={3}>{t("labels")}</Title>
          <Text size="sm" c="dimmed">
            {t("labelsHint")}
          </Text>
        </Stack>
        <Group>
          <Button
            component="a"
            href={`${LABEL_BASE}/${product.id}/label.pdf?layout=single`}
            target="_blank"
            rel="noreferrer"
            variant="light"
            leftSection={<IconTag size={16} />}
          >
            {t("printLabel")}
          </Button>
          <Button
            component="a"
            href={`${LABEL_BASE}/${product.id}/label.pdf?layout=sheet&copies=24`}
            target="_blank"
            rel="noreferrer"
            variant="light"
            leftSection={<IconTag size={16} />}
          >
            {t("printLabelSheet")}
          </Button>
          {needsBarcode && canManage && (
            <Button
              onClick={generateBarcode}
              loading={generating}
              variant="light"
              leftSection={<IconBarcode size={16} />}
            >
              {t("generateBarcodeAction")}
            </Button>
          )}
        </Group>
      </Stack>
    </Card>
  );
}
