"use client";

import {
  ActionIcon,
  Button,
  Card,
  Group,
  NumberInput,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { IconPlus, IconTrash } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { MoneyInput } from "@/components/MoneyInput";
import { ProductSelect } from "@/components/ProductSelect";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useLineEditor, type EditableLine } from "@/hooks/use-line-editor";
import { useResourceCreate, useResourceList } from "@/hooks/use-resource";
import { ApiError } from "@/lib/api";
import { isValidPriceInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import type { Currency, PurchaseOrder, Supplier } from "@/lib/types";

/**
 * FR-3.1: a Manager raises an order — supplier, and lines of product,
 * quantity and (optionally) unit cost.
 *
 * A line's price may be left blank here: the store often does not know it
 * until the deal is agreed, and the detail page fills it in per line. What
 * cannot be left blank is the currency, and nobody chooses it — each line
 * inherits its product's (§4.5 rule 3), which is why the price field only
 * appears once a product is picked.
 */
export function PurchaseOrderForm() {
  const t = useTranslations("purchaseOrders");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const router = useRouter();

  const [supplierId, setSupplierId] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const { lines, updateLine, addLine, removeLine, filled } = useLineEditor();
  const [formError, setFormError] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);

  const suppliers = useResourceList<Supplier>("suppliers", {
    page: 1,
    pageSize: 200,
    isActive: true,
  });
  const create = useResourceCreate<PurchaseOrder, Record<string, unknown>>(
    "purchase-orders",
  );

  function priceError(line: EditableLine): string | null {
    if (!line.unitCost.trim() || !line.product) return null;
    return isValidPriceInput(line.unitCost, line.product.currency)
      ? null
      : line.product.currency === "USD"
        ? tDoc("priceHintUsd")
        : tDoc("priceHintUzs");
  }

  /** Shows the shape the amount must take, in the line's own currency. */
  function priceHint(currency: Currency): string {
    return currency === "USD" ? "0.00" : "0";
  }

  const isValid =
    supplierId !== null &&
    filled.length > 0 &&
    lines.every((line) => priceError(line) === null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setShowErrors(true);
    setFormError(null);
    if (!isValid) return;

    try {
      const order = await create.mutateAsync({
        supplierId,
        note: note.trim() || null,
        lines: filled.map((line) => ({
          productId: line.product!.id,
          quantity: line.quantity,
          // Omitted rather than null: an absent price is "not agreed yet",
          // which the server treats differently from a stated one.
          ...(line.unitCost.trim() ? { unitCost: line.unitCost.trim() } : {}),
        })),
      });
      notifySuccess(tCommon("created"));
      router.push(`/purchase-orders/${order!.id}`);
    } catch (error) {
      if (error instanceof ApiError) setFormError(error.message);
      else setFormError(errorMessage(error, tCommon("retry")));
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="lg" maw={960}>
        <Title order={2}>{t("newTitle")}</Title>

        <ErrorAlert message={formError} />

        <Card withBorder radius="md" padding="lg">
          <Stack gap="md">
            <Select
              label={t("supplier")}
              placeholder={t("filterSupplier")}
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

        <Card withBorder radius="md" padding="lg">
          <Stack gap="md">
            <Group justify="space-between">
              <Text fw={500}>{tDoc("lines")}</Text>
              <Button
                variant="light"
                size="xs"
                leftSection={<IconPlus size={14} />}
                onClick={addLine}
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
                    <Table.Th w={180}>{tDoc("unitCost")}</Table.Th>
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
                            // The price was typed for the old product's
                            // currency, so it cannot follow a new one.
                            updateLine(line.key, { product, unitCost: "" })
                          }
                          placeholder={tDoc("product")}
                        />
                      </Table.Td>
                      <Table.Td>
                        <NumberInput
                          value={line.quantity}
                          onChange={(value) =>
                            updateLine(line.key, { quantity: Number(value) || 1 })
                          }
                          min={1}
                          allowDecimal={false}
                        />
                      </Table.Td>
                      <Table.Td>
                        <MoneyInput
                          value={line.unitCost}
                          onChange={(value) => updateLine(line.key, { unitCost: value })}
                          placeholder={
                            line.product ? priceHint(line.product.currency) : ""
                          }
                          disabled={!line.product}
                          error={priceError(line)}
                          currency={line.product && line.product.currency}
                        />
                      </Table.Td>
                      <Table.Td>
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          aria-label={t("removeLine")}
                          disabled={lines.length === 1}
                          onClick={() => removeLine(line.key)}
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
