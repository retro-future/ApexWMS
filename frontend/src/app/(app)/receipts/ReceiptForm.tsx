"use client";

import {
  ActionIcon,
  Alert,
  Button,
  Card,
  Group,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { IconAlertCircle, IconPlus, IconTrash } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { useCan } from "@/components/MeProvider";
import { MoneyInput } from "@/components/MoneyInput";
import { ProductSelect } from "@/components/ProductSelect";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useSupplierLookup } from "@/hooks/use-lookup";
import { useResourceCreate, useResourceItem, useResourceList } from "@/hooks/use-resource";
import { ApiError } from "@/lib/api";
import { isValidPriceInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type {
  AcquisitionSource,
  Customer,
  GoodsReceipt,
  Location,
  Product,
  PurchaseOrder,
  Supplier,
} from "@/lib/types";

type Line = {
  key: string;
  product: Product | null;
  quantity: number;
  unitCost: string;
};

function emptyLine(): Line {
  return { key: crypto.randomUUID(), product: null, quantity: 1, unitCost: "" };
}

/**
 * FR-3.3, FR-3.3b: opening a receipt.
 *
 * The source is the first question because it changes who the counterparty
 * is: `SUPPLIER` requires a supplier, `TRADE_IN` allows none and may name
 * the walk-in customer instead. The aggregate rejects either mistake, so
 * this form simply never offers the wrong field.
 *
 * With `?purchaseOrderId=` the lines come from the order and there is
 * nothing to edit here — the server pre-fills them from a confirmed PO.
 */
export function ReceiptForm() {
  const t = useTranslations("receipts");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const can = useCan();

  const purchaseOrderId = useSearchParams().get("purchaseOrderId");
  const fromOrder = Boolean(purchaseOrderId);

  // The order already names a supplier; nothing here needs the operator to
  // repeat it, and the server ignores whatever this form would send anyway
  // once a purchase_order_id is given (it always uses the order's supplier).
  const order = useResourceItem<PurchaseOrder>(
    "purchase-orders",
    purchaseOrderId ?? "",
    { enabled: fromOrder && can(Permission.PurchaseOrder.View) },
  );
  const supplierNames = useSupplierLookup();
  const poSupplierId = order.data?.supplierId ?? null;

  const [source, setSource] = useState<AcquisitionSource>("supplier");
  const [supplierId, setSupplierId] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [locationId, setLocationId] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<Line[]>([emptyLine()]);
  const [formError, setFormError] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);

  const reference = { page: 1, pageSize: 200, isActive: true };
  const suppliers = useResourceList<Supplier>("suppliers", reference);
  const locations = useResourceList<Location>("locations", reference);
  const customers = useResourceList<Customer>("customers", reference, {
    enabled: can(Permission.Customer.View),
  });

  const create = useResourceCreate<GoodsReceipt, Record<string, unknown>>(
    "receipts",
  );
  const canPrice = can(Permission.Pricing.Set);

  function updateLine(key: string, patch: Partial<Line>) {
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    );
  }

  /** A serialized line carries no line cost: each handset is priced as it is scanned. */
  function costable(line: Line): boolean {
    return canPrice && line.product?.trackingType === "quantity";
  }

  function priceError(line: Line): string | null {
    if (!costable(line) || !line.unitCost.trim() || !line.product) return null;
    return isValidPriceInput(line.unitCost, line.product.currency)
      ? null
      : line.product.currency === "USD"
        ? tDoc("priceHintUsd")
        : tDoc("priceHintUzs");
  }

  const filled = lines.filter((line) => line.product !== null);
  const isValid =
    locationId !== null &&
    (source === "trade_in" || fromOrder || supplierId !== null) &&
    (fromOrder || filled.length > 0) &&
    lines.every((line) => priceError(line) === null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setShowErrors(true);
    setFormError(null);
    if (!isValid) return;

    try {
      const receipt = await create.mutateAsync({
        locationId,
        acquisitionSource: source,
        // Sent only where the source allows it — the server refuses the
        // other combination outright (FR-3.3b). Omitted entirely when
        // raised from a PO: the server always uses the order's supplier.
        ...(source === "supplier" ? (fromOrder ? {} : { supplierId }) : { customerId }),
        ...(purchaseOrderId ? { purchaseOrderId } : {}),
        ...(fromOrder
          ? {}
          : {
              lines: filled.map((line) => ({
                productId: line.product!.id,
                quantity: line.quantity,
                ...(costable(line) && line.unitCost.trim()
                  ? { unitCost: line.unitCost.trim() }
                  : {}),
              })),
            }),
        note: note.trim() || null,
      });
      notifySuccess(tCommon("created"));
      router.push(`/receipts/${receipt!.id}`);
    } catch (error) {
      if (error instanceof ApiError) setFormError(error.message);
      else setFormError(errorMessage(error, tCommon("retry")));
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="lg" maw={960}>
        <Title order={2}>{t("newTitle")}</Title>

        {formError && (
          <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
            {formError}
          </Alert>
        )}

        <Card withBorder radius="md" padding="lg">
          <Stack gap="md">
            {/* A receipt raised from a PO is always from a supplier. */}
            {!fromOrder && (
              <Stack gap="2xs">
                <Text size="sm" fw={500}>
                  {t("source")}
                </Text>
                <SegmentedControl
                  value={source}
                  onChange={(value) => setSource(value as AcquisitionSource)}
                  data={["supplier", "trade_in"].map((value) => ({
                    value,
                    label: tDoc(`source.${value}`),
                  }))}
                  w={{ base: "100%", sm: 320 }}
                />
                <Text size="xs" c="dimmed">
                  {t("sourceHint")}
                </Text>
              </Stack>
            )}

            {fromOrder ? (
              <TextInput
                label={t("supplier")}
                value={poSupplierId ? (supplierNames.get(poSupplierId) ?? tCommon("none")) : tCommon("none")}
                disabled
              />
            ) : source === "supplier" ? (
              <Select
                label={t("supplier")}
                value={supplierId}
                onChange={setSupplierId}
                searchable
                required
                error={showErrors && !supplierId ? tCommon("required") : null}
                data={(suppliers.data?.items ?? []).map((supplier) => ({
                  value: supplier.id,
                  label: supplier.name,
                }))}
                w={{ base: "100%", sm: 360 }}
              />
            ) : (
              can(Permission.Customer.View) && (
                <Select
                  label={t("customer")}
                  description={t("customerHint")}
                  value={customerId}
                  onChange={setCustomerId}
                  searchable
                  clearable
                  data={(customers.data?.items ?? []).map((customer) => ({
                    value: customer.id,
                    label: customer.fullName,
                  }))}
                  w={{ base: "100%", sm: 360 }}
                />
              )
            )}

            <Select
              label={t("location")}
              value={locationId}
              onChange={setLocationId}
              searchable
              required
              error={showErrors && !locationId ? tCommon("required") : null}
              data={(locations.data?.items ?? []).map((location) => ({
                value: location.id,
                label: location.name,
              }))}
              w={{ base: "100%", sm: 360 }}
            />

            <Textarea
              label={tDoc("note")}
              description={tCommon("optional")}
              value={note}
              onChange={(event) => setNote(event.currentTarget.value)}
              autosize
              minRows={2}
            />
          </Stack>
        </Card>

        {fromOrder ? (
          <Alert variant="light" icon={<IconAlertCircle size={18} />}>
            {t("fromOrderHint")}
          </Alert>
        ) : (
          <Card withBorder radius="md" padding="lg">
            <Stack gap="md">
              <Group justify="space-between">
                <Text fw={500}>{tDoc("lines")}</Text>
                <Button
                  variant="light"
                  size="xs"
                  leftSection={<IconPlus size={14} />}
                  onClick={() => setLines((current) => [...current, emptyLine()])}
                >
                  {t("addLine")}
                </Button>
              </Group>

              {showErrors && filled.length === 0 && (
                <Text size="sm" c="red">
                  {t("linesRequired")}
                </Text>
              )}

              <TableScrollArea>
                <Table verticalSpacing="sm" miw={640}>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{tDoc("product")}</Table.Th>
                      <Table.Th w={120}>{tDoc("quantity")}</Table.Th>
                      {canPrice && <Table.Th w={180}>{tDoc("unitCost")}</Table.Th>}
                      <Table.Th w={48} />
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {lines.map((line) => (
                      <Table.Tr key={line.key}>
                        <Table.Td>
                          <ProductSelect
                            value={line.product?.id ?? null}
                            onChange={(product) =>
                              updateLine(line.key, { product, unitCost: "" })
                            }
                            placeholder={tDoc("product")}
                          />
                        </Table.Td>
                        <Table.Td>
                          <NumberInput
                            value={line.quantity}
                            onChange={(value) =>
                              updateLine(line.key, {
                                quantity: Number(value) || 1,
                              })
                            }
                            min={1}
                            allowDecimal={false}
                          />
                        </Table.Td>
                        {canPrice && (
                          <Table.Td>
                            <MoneyInput
                              value={line.unitCost}
                              onChange={(value) => updateLine(line.key, { unitCost: value })}
                              disabled={!costable(line)}
                              placeholder={
                                line.product?.trackingType === "serial"
                                  ? t("unitCostSerialHint")
                                  : line.product?.currency === "USD"
                                    ? "0.00"
                                    : "0"
                              }
                              error={priceError(line)}
                              currency={costable(line) && line.product?.currency}
                            />
                          </Table.Td>
                        )}
                        <Table.Td>
                          <ActionIcon
                            variant="subtle"
                            color="red"
                            aria-label={t("removeLine")}
                            disabled={lines.length === 1}
                            onClick={() =>
                              setLines((current) =>
                                current.filter((row) => row.key !== line.key),
                              )
                            }
                          >
                            <IconTrash size={16} />
                          </ActionIcon>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </TableScrollArea>
            </Stack>
          </Card>
        )}

        <Group justify="flex-end">
          <Button variant="default" onClick={() => router.back()}>
            {tCommon("cancel")}
          </Button>
          <Button type="submit" loading={create.isPending}>
            {tCommon("create")}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
