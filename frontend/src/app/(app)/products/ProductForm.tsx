"use client";

import {
  Alert,
  Button,
  Card,
  Checkbox,
  Group,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { IconInfoCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { useCan } from "@/components/MeProvider";
import { useResourceCreate, useResourceUpdate } from "@/hooks/use-resource";
import { ApiError } from "@/lib/api";
import { isValidPriceInput, moneyToInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { Currency, Product, TrackingType } from "@/lib/types";

type Values = {
  sku: string;
  name: string;
  brand: string;
  model: string;
  trackingType: TrackingType;
  currency: Currency;
  barcode: string;
  generateBarcode: boolean;
  price: string;
  isActive: boolean;
};

/** FR-2.6: a phone is priced in dollars, an accessory in so'm. */
const DEFAULT_CURRENCY: Record<TrackingType, Currency> = {
  serial: "USD",
  quantity: "UZS",
};

const SKU_PATTERN = /^[A-Za-z0-9._\-/]{1,64}$/;
const BARCODE_LENGTHS = new Set([8, 12, 13, 14]);

export function ProductForm({ product }: { product?: Product }) {
  const t = useTranslations("products");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const can = useCan();

  const isEdit = Boolean(product);
  const readOnly = !can(Permission.Catalog.Manage);
  const [formError, setFormError] = useState<string | null>(null);

  const create = useResourceCreate<Product, Record<string, unknown>>("products");
  const update = useResourceUpdate<Product, Record<string, unknown>>("products");

  const initialCurrency = product?.currency ?? DEFAULT_CURRENCY.serial;

  const form = useForm<Values>({
    initialValues: {
      sku: product?.sku ?? "",
      name: product?.name ?? "",
      brand: product?.brand ?? "",
      model: product?.model ?? "",
      trackingType: product?.trackingType ?? "serial",
      currency: initialCurrency,
      barcode: product?.barcode ?? "",
      generateBarcode: false,
      price: moneyToInput(product?.defaultSalePrice),
      isActive: product?.isActive ?? true,
    },
    validate: {
      sku: (value) =>
        isEdit || !value.trim() || SKU_PATTERN.test(value.trim())
          ? null
          : tCommon("required"),
      name: (value) => (value.trim() ? null : tCommon("required")),
      barcode: (value, values) => {
        const digits = value.replace(/[\s-]/g, "");
        if (!digits || values.trackingType === "serial" || values.generateBarcode)
          return null;
        return BARCODE_LENGTHS.has(digits.length) ? null : t("barcodeHint");
      },
      price: (value, values) => {
        if (!value.trim()) return null;
        return isValidPriceInput(value, values.currency)
          ? null
          : values.currency === "USD"
            ? t("priceHintUsd")
            : t("priceHintUzs");
      },
    },
  });

  const isSerial = form.values.trackingType === "serial";

  function changeTracking(value: string | null) {
    if (!value) return;
    const tracking = value as TrackingType;
    form.setFieldValue("trackingType", tracking);
    form.setFieldValue("currency", DEFAULT_CURRENCY[tracking]);
    // A serial product is identified by IMEI; the backend rejects a barcode.
    if (tracking === "serial") form.setFieldValue("barcode", "");
  }

  async function submit(values: Values) {
    setFormError(null);

    // Sending an explicit null clears the field; the backend only touches
    // what it actually receives (it reads model_fields_set).
    const shared = {
      name: values.name.trim(),
      brand: values.brand.trim() || null,
      model: values.model.trim() || null,
      barcode: isSerial ? null : values.barcode.replace(/[\s-]/g, "") || null,
      // A string, never a float — a JSON float is a validation error.
      defaultSalePrice: values.price.trim() || null,
    };

    try {
      if (product) {
        await update.mutateAsync({
          id: product.id,
          payload: { ...shared, isActive: values.isActive },
        });
        notifySuccess(tCommon("updated"));
        router.refresh();
      } else {
        const wantsGeneratedBarcode = !isSerial && values.generateBarcode;
        const created = await create.mutateAsync({
          ...shared,
          barcode: wantsGeneratedBarcode ? undefined : shared.barcode,
          generateBarcode: wantsGeneratedBarcode || undefined,
          sku: values.sku.trim() || undefined,
          trackingType: values.trackingType,
          currency: values.currency,
        });
        notifySuccess(tCommon("created"));
        router.push(created ? `/products/${created.id}` : "/products");
      }
    } catch (err) {
      if (err instanceof ApiError && err.isConflict) {
        const message = err.message.toLowerCase();
        if (message.includes("sku")) form.setFieldError("sku", err.message);
        else if (message.includes("barcode"))
          form.setFieldError("barcode", err.message);
        else setFormError(err.message);
        return;
      }
      setFormError(errorMessage(err, tCommon("retry")));
    }
  }

  const busy = create.isPending || update.isPending;

  return (
    <form onSubmit={form.onSubmit(submit)} noValidate>
      <Stack gap="lg" maw={720}>
        <Stack gap="3xs">
          <Title order={2}>{isEdit ? t("editTitle") : t("newTitle")}</Title>
          {isEdit && (
            <Text size="sm" c="dimmed">
              {t("immutableAfterCreate")}
            </Text>
          )}
        </Stack>

        <ErrorAlert message={formError} />

        <Card withBorder radius="md" padding="lg">
          <Stack gap="md">
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <TextInput
                label={t("sku")}
                description={isEdit ? undefined : t("skuHintAuto")}
                // Hint below the input, so a two-line hint doesn't push this
                // field out of alignment with Name beside it.
                inputWrapperOrder={["label", "input", "description", "error"]}
                disabled={isEdit || readOnly}
                {...form.getInputProps("sku")}
              />
              <TextInput
                label={t("name")}
                disabled={readOnly}
                {...form.getInputProps("name")}
              />
              <TextInput
                label={`${t("brand")} (${tCommon("optional")})`}
                disabled={readOnly}
                {...form.getInputProps("brand")}
              />
              <TextInput
                label={`${t("model")} (${tCommon("optional")})`}
                disabled={readOnly}
                {...form.getInputProps("model")}
              />
            </SimpleGrid>
          </Stack>
        </Card>

        <Card withBorder radius="md" padding="lg">
          <Stack gap="md">
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <Select
                label={t("trackingType")}
                value={form.values.trackingType}
                onChange={changeTracking}
                // Immutable once created: stock movements from M3 depend on it.
                disabled={isEdit || readOnly}
                allowDeselect={false}
                data={[
                  { value: "serial", label: t("serial") },
                  { value: "quantity", label: t("quantity") },
                ]}
              />
              <Select
                label={t("currency")}
                disabled={isEdit || readOnly}
                allowDeselect={false}
                data={["UZS", "USD"]}
                {...form.getInputProps("currency")}
              />
            </SimpleGrid>

            <TextInput
              label={t("price")}
              placeholder={form.values.currency === "USD" ? "599.00" : "12000"}
              description={
                form.values.currency === "USD"
                  ? t("priceHintUsd")
                  : t("priceHintUzs")
              }
              inputMode="decimal"
              disabled={readOnly}
              {...form.getInputProps("price")}
            />

            {isSerial ? (
              <Alert
                variant="light"
                color="blue"
                icon={<IconInfoCircle size={18} />}
              >
                {t("noBarcodeForSerial")}
              </Alert>
            ) : (
              <Stack gap="xs">
                {!isEdit && (
                  <Checkbox
                    label={t("generateBarcode")}
                    disabled={readOnly}
                    checked={form.values.generateBarcode}
                    onChange={(event) =>
                      form.setFieldValue(
                        "generateBarcode",
                        event.currentTarget.checked,
                      )
                    }
                  />
                )}
                <TextInput
                  label={`${t("barcode")} (${tCommon("optional")})`}
                  description={t("barcodeHint")}
                  inputMode="numeric"
                  disabled={readOnly || (!isEdit && form.values.generateBarcode)}
                  {...form.getInputProps("barcode")}
                />
              </Stack>
            )}

            {isEdit && (
              <Switch
                label={t("isActive")}
                disabled={readOnly}
                checked={form.values.isActive}
                onChange={(event) =>
                  form.setFieldValue("isActive", event.currentTarget.checked)
                }
              />
            )}
          </Stack>
        </Card>

        {!readOnly && (
          <Group justify="flex-end">
            <Button variant="default" onClick={() => router.push("/products")}>
              {tCommon("cancel")}
            </Button>
            <Button type="submit" loading={busy}>
              {isEdit ? tCommon("save") : tCommon("create")}
            </Button>
          </Group>
        )}
      </Stack>
    </form>
  );
}
