"use client";

import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Group,
  List,
  Loader,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconAlertCircle, IconTrash } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ScanConsole } from "@/app/(app)/receipts/ScanConsole";
import { DocumentStatusBadge } from "@/components/DocumentStatusBadge";
import { FormModal } from "@/components/FormModal";
import { useCan } from "@/components/MeProvider";
import { ReasonModal } from "@/components/ReasonModal";
import { Subtotals } from "@/components/Subtotals";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useDocumentAction } from "@/hooks/use-document";
import {
  useCustomerLookup,
  useLocationLookup,
  useProductLookup,
  useSupplierLookup,
} from "@/hooks/use-lookup";
import { useResourceItem } from "@/hooks/use-resource";
import { formatMoney, minorToInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import {
  confirmBlockers,
  isEditable,
  isSerial,
  referenceCosts,
  type ReferenceCost,
} from "@/lib/receipts";
import type {
  GoodsReceipt,
  PurchaseOrder,
  ReceivedUnit,
  ScanResult,
} from "@/lib/types";

export default function ReceiptPage() {
  const t = useTranslations("receipts");
  const tScan = useTranslations("receipts.scan");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { id } = useParams<{ id: string }>();
  const can = useCan();
  const queryClient = useQueryClient();

  const canPrice = can(Permission.Pricing.Set);

  const query = useResourceItem<GoodsReceipt>("receipts", id);
  const products = useProductLookup();
  const suppliers = useSupplierLookup();
  const customers = useCustomerLookup();
  const locations = useLocationLookup();
  // A receipt raised from a PO carries that order's agreed prices, offered
  // back as a default at the point where per-unit cost is actually entered.
  const purchaseOrder = useResourceItem<PurchaseOrder>(
    "purchase-orders",
    query.data?.purchaseOrderId ?? "",
    { enabled: canPrice && Boolean(query.data?.purchaseOrderId) },
  );

  const [pricing, setPricing] = useState<{
    unit: ReceivedUnit;
    productId: string;
  } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmRefusal, setConfirmRefusal] = useState<string | null>(null);

  const confirm = useDocumentAction<GoodsReceipt>("receipts", id, {
    path: "/confirm",
  });
  const cancel = useDocumentAction<GoodsReceipt, { reason: string | null }>(
    "receipts",
    id,
    { path: "/cancel" },
  );
  const unscan = useDocumentAction<null, { imei: string }>("receipts", id, {
    method: "DELETE",
    path: (payload) => `/scan/${payload.imei}`,
  });

  /**
   * A scan patches the cached document instead of refetching it: the scan
   * response already carries the accepted handset and the running count,
   * and a round trip between beeps is exactly what §6 budgets against.
   */
  function applyScan(result: ScanResult) {
    queryClient.setQueryData<GoodsReceipt>(["receipts", "item", id], (current) =>
      current
        ? {
            ...current,
            lines: current.lines.map((line) =>
              line.id === result.lineId
                ? {
                    ...line,
                    scannedCount: result.scannedCount,
                    units: [
                      ...line.units.filter((unit) => unit.imei !== result.unit.imei),
                      result.unit,
                    ],
                  }
                : line,
            ),
          }
        : current,
    );
  }

  if (query.isLoading) {
    return (
      <Center p="xl">
        <Loader size="sm" />
      </Center>
    );
  }

  const receipt = query.data;
  if (query.isError || !receipt) {
    return (
      <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
        {query.error instanceof Error ? query.error.message : t("notFound")}
      </Alert>
    );
  }

  const draft = isEditable(receipt.status);
  const blockers = confirmBlockers(receipt);
  const refCosts = referenceCosts(purchaseOrder.data);
  const from =
    receipt.acquisitionSource === "supplier"
      ? suppliers.get(receipt.supplierId)
      : customers.get(receipt.customerId);
  const units = receipt.lines.flatMap((line) =>
    line.units.map((unit) => ({ unit, productId: line.productId })),
  );

  async function runConfirm() {
    setActionError(null);
    setConfirmRefusal(null);
    try {
      await confirm.mutateAsync(undefined as never);
      notifySuccess(tDoc("confirmed"));
      setConfirming(false);
    } catch (error) {
      // FR-3.8 / FR-3.10 name the offending lines and IMEIs, so the refusal
      // is a worklist and belongs on the page, not in a toast that vanishes.
      const message = errorMessage(error, tCommon("retry"));
      setConfirming(false);
      setConfirmRefusal(message);
    }
  }

  async function runCancel(reason: string | null) {
    setActionError(null);
    try {
      await cancel.mutateAsync({ reason });
      notifySuccess(tDoc("cancelled"));
      setCancelling(false);
    } catch (error) {
      setActionError(errorMessage(error, tCommon("retry")));
    }
  }

  async function removeUnit(imei: string) {
    try {
      await unscan.mutateAsync({ imei });
      notifySuccess(tScan("unscanned", { imei }));
    } catch (error) {
      setActionError(errorMessage(error, tCommon("retry")));
    }
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <Stack gap="2xs">
          <Group gap="sm">
            <Title order={2}>{receipt.number}</Title>
            <DocumentStatusBadge status={receipt.status} />
            <Badge
              size="sm"
              variant="light"
              color={receipt.acquisitionSource === "supplier" ? "blue" : "grape"}
            >
              {tDoc(`source.${receipt.acquisitionSource}`)}
            </Badge>
          </Group>
          <Text size="sm" c="dimmed">
            {from ?? tCommon("none")}
            {" · "}
            {t("location")}: {locations.get(receipt.locationId) ?? tCommon("none")}
            {" · "}
            {tDoc("created")}: {new Date(receipt.createdAt).toLocaleString()}
          </Text>
          {receipt.note && <Text size="sm">{receipt.note}</Text>}
        </Stack>

        <Group gap="sm">
          {draft && can(Permission.Receiving.Manage) && (
            <Button onClick={() => setConfirming(true)}>
              {tDoc("confirmAction")}
            </Button>
          )}
          {receipt.status === "confirmed" && can(Permission.Document.Cancel) && (
            <Button color="red" variant="light" onClick={() => setCancelling(true)}>
              {tDoc("cancelAction")}
            </Button>
          )}
        </Group>
      </Group>

      {receipt.status === "cancelled" && (
        <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
          {tDoc("cancelledNotice")}
        </Alert>
      )}

      {actionError && (
        <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
          {actionError}
        </Alert>
      )}

      {confirmRefusal && (
        <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
          {confirmRefusal}
        </Alert>
      )}

      {draft && !blockers.isReady && (
        <Alert variant="light" color="yellow" icon={<IconAlertCircle size={18} />}>
          <Stack gap="2xs">
            <Text fw={500}>{t("blockersTitle")}</Text>
            <List size="sm">
              {blockers.shortLines.map((line) => (
                <List.Item key={line.id}>
                  {t("blockerShort", {
                    product: products.get(line.productId) ?? tCommon("none"),
                    scanned: line.scannedCount,
                    expected: line.quantity,
                  })}
                </List.Item>
              ))}
              {blockers.unpricedUnits.map((unit) => (
                <List.Item key={unit.id}>
                  {t("blockerUnpriced", {
                    imei: unit.imei,
                    condition: tDoc(`condition.${unit.condition}`),
                  })}
                </List.Item>
              ))}
            </List>
          </Stack>
        </Alert>
      )}

      {draft && can(Permission.Receiving.Manage) &&
        receipt.lines.some(isSerial) && (
          <ScanConsole
            receipt={receipt}
            referenceCosts={refCosts}
            onScanned={applyScan}
          />
        )}

      {!draft && (
        <Text size="sm" c="dimmed">
          {tScan("readOnly")}
        </Text>
      )}

      <Card withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Text fw={500}>{tDoc("lines")}</Text>
          <TableScrollArea>
            <Table verticalSpacing="sm" miw={560}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{tDoc("product")}</Table.Th>
                  <Table.Th>{tDoc("quantity")}</Table.Th>
                  <Table.Th>{t("scannedUnits")}</Table.Th>
                  <Table.Th>{tDoc("unitCost")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {receipt.lines.map((line) => (
                  <Table.Tr key={line.id}>
                    <Table.Td>
                      {products.get(line.productId) ?? tCommon("none")}
                    </Table.Td>
                    <Table.Td>{line.quantity}</Table.Td>
                    <Table.Td>
                      {isSerial(line)
                        ? t("progress", {
                            scanned: line.scannedCount,
                            expected: line.quantity,
                          })
                        : tCommon("none")}
                    </Table.Td>
                    <Table.Td>
                      {/* Absent, not zero, without Cost.View (FR-1.7). */}
                      {line.unitCostMinor === null ||
                      line.unitCostMinor === undefined
                        ? tCommon("none")
                        : formatMoney(line.unitCostMinor, line.currency)}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </TableScrollArea>

          {receipt.subtotals.length > 0 && (
            <Group justify="space-between" wrap="wrap">
              <Text size="sm" c="dimmed">
                {tDoc("subtotalsHint")}
              </Text>
              <Subtotals subtotals={receipt.subtotals} size="md" fw={600} />
            </Group>
          )}
        </Stack>
      </Card>

      <Card withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Text fw={500}>{t("scannedUnits")}</Text>

          {units.length === 0 ? (
            <Text size="sm" c="dimmed">
              {tScan("empty")}
            </Text>
          ) : (
            <TableScrollArea>
              <Table verticalSpacing="sm" miw={640}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>IMEI</Table.Th>
                    <Table.Th>{tDoc("product")}</Table.Th>
                    <Table.Th>{tScan("condition")}</Table.Th>
                    <Table.Th>{tScan("askingPrice")}</Table.Th>
                    <Table.Th>{tScan("acquisitionCost")}</Table.Th>
                    <Table.Th />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {units.map(({ unit, productId }) => (
                    <Table.Tr key={unit.id}>
                      <Table.Td>
                        <Text size="sm" ff="monospace">
                          {unit.imei}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        {products.get(productId) ?? tCommon("none")}
                      </Table.Td>
                      <Table.Td>
                        <Group gap="2xs">
                          <Text size="sm">
                            {tDoc(`condition.${unit.condition}`)}
                          </Text>
                          {unit.needsAskingPrice && (
                            <Badge size="xs" variant="light" color="yellow">
                              {tScan("needsPrice")}
                            </Badge>
                          )}
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        {unit.askingPriceMinor === null
                          ? tCommon("none")
                          : formatMoney(unit.askingPriceMinor, unit.currency)}
                      </Table.Td>
                      <Table.Td>
                        {unit.acquisitionCostMinor === null ||
                        unit.acquisitionCostMinor === undefined
                          ? tCommon("none")
                          : formatMoney(unit.acquisitionCostMinor, unit.currency)}
                        {unit.cashPaid && (
                          <Text size="xs" c="dimmed">
                            {tScan("cashPaid")}: {unit.cashPaid}
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td>
                        <Group gap="2xs" justify="flex-end" wrap="nowrap">
                          {draft && can(Permission.Pricing.Set) && (
                            <Button
                              size="compact-sm"
                              variant="subtle"
                              onClick={() => setPricing({ unit, productId })}
                            >
                              {tScan("priceUnit")}
                            </Button>
                          )}
                          {draft && can(Permission.Receiving.Manage) && (
                            <ActionIcon
                              variant="subtle"
                              color="red"
                              aria-label={tScan("unscan")}
                              loading={unscan.isPending}
                              onClick={() => removeUnit(unit.imei)}
                            >
                              <IconTrash size={16} />
                            </ActionIcon>
                          )}
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </TableScrollArea>
          )}

          {units.some((entry) => entry.unit.needsAskingPrice) && (
            <Text size="sm" c="dimmed">
              {tScan("needsPriceHint")}
            </Text>
          )}
        </Stack>
      </Card>

      {!draft && (
        <Text size="sm" c="dimmed">
          {tDoc("immutable")}
        </Text>
      )}

      {pricing && (
        <PriceUnitModal
          receiptId={receipt.id}
          unit={pricing.unit}
          reference={refCosts.get(pricing.productId)}
          onClose={() => setPricing(null)}
        />
      )}

      <ReasonModal
        opened={confirming}
        onClose={() => setConfirming(false)}
        title={t("confirmTitle")}
        description={t("confirmBody")}
        submitLabel={tDoc("confirmAction")}
        busy={confirm.isPending}
        error={actionError}
        onSubmit={runConfirm}
      />

      <ReasonModal
        opened={cancelling}
        onClose={() => setCancelling(false)}
        title={t("cancelTitle")}
        description={t("cancelBody")}
        submitLabel={tDoc("cancelAction")}
        color="red"
        busy={cancel.isPending}
        error={actionError}
        onSubmit={runCancel}
      />
    </Stack>
  );
}

/** FR-3.4b: an Owner or Manager prices what the Storekeeper scanned. */
function PriceUnitModal({
  receiptId,
  unit,
  reference,
  onClose,
}: {
  receiptId: string;
  unit: ReceivedUnit;
  reference: ReferenceCost | undefined;
  onClose: () => void;
}) {
  const tScan = useTranslations("receipts.scan");
  const tCommon = useTranslations("common");

  const [cost, setCost] = useState(
    unit.acquisitionCost ??
      (reference ? minorToInput(reference.minor, reference.currency) : ""),
  );
  const [asking, setAsking] = useState(unit.askingPrice ?? "");
  const [cash, setCash] = useState("");
  const [error, setError] = useState<string | null>(null);

  const price = useDocumentAction<
    ReceivedUnit,
    {
      acquisitionCost?: string;
      askingPrice?: string;
      cashPaid?: string;
      cashPaidCurrency?: "UZS";
    }
  >("receipts", receiptId, {
    method: "PATCH",
    path: () => `/scan/${unit.imei}`,
  });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await price.mutateAsync({
        ...(cost.trim() ? { acquisitionCost: cost.trim() } : {}),
        ...(asking.trim() ? { askingPrice: asking.trim() } : {}),
        ...(cash.trim() ? { cashPaid: cash.trim(), cashPaidCurrency: "UZS" } : {}),
      });
      notifySuccess(tCommon("saved"));
      onClose();
    } catch (thrown) {
      setError(errorMessage(thrown, tCommon("retry")));
    }
  }

  return (
    <FormModal
      opened
      onClose={onClose}
      title={tScan("priceUnitTitle", { imei: unit.imei })}
      onSubmit={submit}
      busy={price.isPending}
      error={error}
      submitLabel={tCommon("save")}
    >
      <TextInput
        label={tScan("acquisitionCost")}
        description={
          !unit.acquisitionCost && reference
            ? tScan("poReferenceHint", {
                price: formatMoney(reference.minor, reference.currency),
              })
            : undefined
        }
        value={cost}
        onChange={(event) => setCost(event.currentTarget.value)}
        rightSection={
          <Text size="xs" c="dimmed">
            {unit.currency}
          </Text>
        }
        rightSectionWidth={44}
        data-autofocus
      />
      <TextInput
        label={tScan("askingPrice")}
        value={asking}
        onChange={(event) => setAsking(event.currentTarget.value)}
        rightSection={
          <Text size="xs" c="dimmed">
            {unit.currency}
          </Text>
        }
        rightSectionWidth={44}
      />
      <TextInput
        label={tScan("cashPaid")}
        description={tScan("cashPaidHint")}
        value={cash}
        onChange={(event) => setCash(event.currentTarget.value)}
        rightSection={
          <Text size="xs" c="dimmed">
            UZS
          </Text>
        }
        rightSectionWidth={44}
      />
    </FormModal>
  );
}
