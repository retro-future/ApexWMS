"use client";

import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconAlertCircle, IconPackageImport } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { DocumentStatusBadge } from "@/components/DocumentStatusBadge";
import { FormModal } from "@/components/FormModal";
import { useCan } from "@/components/MeProvider";
import { ReasonModal } from "@/components/ReasonModal";
import { Subtotals } from "@/components/Subtotals";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useDocumentAction } from "@/hooks/use-document";
import { useProductLookup, useSupplierLookup } from "@/hooks/use-lookup";
import { useResourceItem } from "@/hooks/use-resource";
import { formatMoney, isValidPriceInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import { isEditable } from "@/lib/receipts";
import type { Fulfilment, PurchaseOrder, PurchaseOrderLine } from "@/lib/types";

const FULFILMENT_COLOR: Record<Fulfilment, string> = {
  pending: "gray",
  partial: "yellow",
  complete: "teal",
};

export default function PurchaseOrderPage() {
  const t = useTranslations("purchaseOrders");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { id } = useParams<{ id: string }>();
  const can = useCan();

  const query = useResourceItem<PurchaseOrder>("purchase-orders", id);
  const suppliers = useSupplierLookup();
  const products = useProductLookup();

  const [pricing, setPricing] = useState<PurchaseOrderLine | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const confirm = useDocumentAction<PurchaseOrder>("purchase-orders", id, {
    path: "/confirm",
  });
  const cancel = useDocumentAction<PurchaseOrder, { reason: string | null }>(
    "purchase-orders",
    id,
    { path: "/cancel" },
  );

  if (query.isLoading) {
    return (
      <Center p="xl">
        <Loader size="sm" />
      </Center>
    );
  }

  const order = query.data;
  if (query.isError || !order) {
    return (
      <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
        {query.error instanceof Error ? query.error.message : t("notFound")}
      </Alert>
    );
  }

  const draft = isEditable(order.status);
  const unpriced = order.lines.filter((line) => line.unitCost === null);
  const canManage = can(Permission.PurchaseOrder.Manage);

  async function run(
    action: { mutateAsync: (payload: never) => Promise<unknown> },
    payload: unknown,
    message: string,
    close: () => void,
  ) {
    setActionError(null);
    try {
      await action.mutateAsync(payload as never);
      notifySuccess(message);
      close();
    } catch (error) {
      setActionError(errorMessage(error, tCommon("retry")));
    }
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <Stack gap="2xs">
          <Group gap="sm">
            <Title order={2}>{order.number}</Title>
            <DocumentStatusBadge status={order.status} />
            <Badge
              size="sm"
              variant="light"
              color={FULFILMENT_COLOR[order.fulfilment]}
            >
              {tDoc(`fulfilment.${order.fulfilment}`)}
            </Badge>
          </Group>
          <Text size="sm" c="dimmed">
            {t("supplier")}: {suppliers.get(order.supplierId) ?? tCommon("none")}
            {" · "}
            {tDoc("created")}: {new Date(order.createdAt).toLocaleString()}
          </Text>
          {order.note && <Text size="sm">{order.note}</Text>}
        </Stack>

        <Group gap="sm">
          {order.status === "confirmed" && can(Permission.Receiving.Manage) && (
            <Button
              component={Link}
              href={`/receipts/new?purchaseOrderId=${order.id}`}
              variant="light"
              leftSection={<IconPackageImport size={16} />}
            >
              {t("receiveAgainst")}
            </Button>
          )}
          {draft && canManage && (
            <Button onClick={() => setConfirming(true)}>
              {tDoc("confirmAction")}
            </Button>
          )}
          {order.status === "confirmed" && can(Permission.Document.Cancel) && (
            <Button color="red" variant="light" onClick={() => setCancelling(true)}>
              {tDoc("cancelAction")}
            </Button>
          )}
        </Group>
      </Group>

      {order.status === "cancelled" && (
        <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
          {tDoc("cancelledNotice")}
        </Alert>
      )}

      {draft && unpriced.length > 0 && (
        <Alert variant="light" color="yellow" icon={<IconAlertCircle size={18} />}>
          {t("unpricedWarning")}
        </Alert>
      )}

      <Card withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Text fw={500}>{tDoc("lines")}</Text>

          <TableScrollArea>
            <Table verticalSpacing="sm" miw={640}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{tDoc("product")}</Table.Th>
                  <Table.Th>{t("ordered")}</Table.Th>
                  <Table.Th>{t("received")}</Table.Th>
                  <Table.Th>{tDoc("unitCost")}</Table.Th>
                  <Table.Th>{tDoc("lineTotal")}</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {order.lines.map((line) => (
                  <Table.Tr key={line.id}>
                    <Table.Td>
                      {products.get(line.productId) ?? tCommon("none")}
                    </Table.Td>
                    <Table.Td>{line.quantity}</Table.Td>
                    <Table.Td>
                      <Text
                        size="sm"
                        c={
                          line.receivedQuantity >= line.quantity
                            ? "teal"
                            : undefined
                        }
                      >
                        {line.receivedQuantity}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      {line.unitCostMinor === null ? (
                        <Badge size="sm" variant="light" color="yellow">
                          {t("unpriced")}
                        </Badge>
                      ) : (
                        formatMoney(line.unitCostMinor, line.currency)
                      )}
                    </Table.Td>
                    <Table.Td>
                      {line.totalCostMinor === null
                        ? tCommon("none")
                        : formatMoney(line.totalCostMinor, line.currency)}
                    </Table.Td>
                    <Table.Td>
                      {draft && can(Permission.Pricing.Set) && (
                        <Button
                          size="compact-sm"
                          variant="subtle"
                          onClick={() => setPricing(line)}
                        >
                          {t("priceLine")}
                        </Button>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </TableScrollArea>

          <Group justify="space-between" wrap="wrap">
            <Text size="sm" c="dimmed">
              {tDoc("subtotalsHint")}
            </Text>
            <Subtotals subtotals={order.subtotals} size="md" fw={600} />
          </Group>
        </Stack>
      </Card>

      {!draft && (
        <Text size="sm" c="dimmed">
          {tDoc("immutable")}
        </Text>
      )}

      {pricing && (
        <PriceLineModal
          orderId={order.id}
          line={pricing}
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
        onSubmit={() =>
          run(confirm, undefined, tDoc("confirmed"), () => setConfirming(false))
        }
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
        onSubmit={(reason) =>
          run(cancel, { reason }, tDoc("cancelled"), () => setCancelling(false))
        }
      />
    </Stack>
  );
}

/** FR-3.1: filling in a price the order was raised without. */
function PriceLineModal({
  orderId,
  line,
  onClose,
}: {
  orderId: string;
  line: PurchaseOrderLine;
  onClose: () => void;
}) {
  const t = useTranslations("purchaseOrders");
  const tCommon = useTranslations("common");
  const tDoc = useTranslations("documents");

  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const price = useDocumentAction<PurchaseOrder, { unitCost: string }>(
    "purchase-orders",
    orderId,
    { method: "PATCH", path: () => `/lines/${line.id}` },
  );

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!isValidPriceInput(value, line.currency)) {
      setError(
        line.currency === "USD" ? tDoc("priceHintUsd") : tDoc("priceHintUzs"),
      );
      return;
    }
    try {
      await price.mutateAsync({ unitCost: value.trim() });
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
      title={t("priceLineTitle")}
      onSubmit={submit}
      busy={price.isPending}
      error={error}
      submitLabel={tCommon("save")}
    >
      <TextInput
        label={tDoc("unitCost")}
        description={t("priceLineHint")}
        value={value}
        onChange={(event) => setValue(event.currentTarget.value)}
        placeholder={line.currency === "USD" ? "0.00" : "0"}
        rightSection={
          <Text size="xs" c="dimmed">
            {line.currency}
          </Text>
        }
        rightSectionWidth={44}
        data-autofocus
      />
    </FormModal>
  );
}
