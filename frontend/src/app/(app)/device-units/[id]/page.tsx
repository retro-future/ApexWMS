"use client";

import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { useCan } from "@/components/MeProvider";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useDocumentAction } from "@/hooks/use-document";
import { useLocationLookup } from "@/hooks/use-lookup";
import { useResourceItem, useResourceList } from "@/hooks/use-resource";
import { apiGet, apiSend } from "@/lib/api";
import { isValidPriceInput } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type {
  Customer,
  DeviceCondition,
  DeviceUnit,
  Location,
  PriceChange,
  SalesInvoice,
} from "@/lib/types";

const CONDITIONS: DeviceCondition[] = ["new", "refurbished", "used"];

/** A handset that has left stock is settled: no repricing, no re-grading. */
const ON_HAND = new Set(["in_stock", "reserved"]);

export default function DeviceUnitPage() {
  const t = useTranslations("deviceUnits");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const tSell = useTranslations("invoices.sell");
  const { id } = useParams<{ id: string }>();
  const can = useCan();

  const query = useResourceItem<DeviceUnit>("device-units", id);
  const locations = useLocationLookup();

  const canPrice = can(Permission.Pricing.Set);
  // Keyed under the unit so a reprice invalidates the log along with it.
  const history = useQuery<PriceChange[]>({
    queryKey: ["device-units", "item", id, "price-history"],
    queryFn: () => apiGet<PriceChange[]>(`/device-units/${id}/price-history`),
    enabled: canPrice,
  });

  const [repricing, setRepricing] = useState(false);
  const [regrading, setRegrading] = useState(false);
  const [selling, setSelling] = useState(false);

  if (query.isLoading) {
    return (
      <Center p="xl">
        <Loader size="sm" />
      </Center>
    );
  }

  const unit = query.data;
  if (query.isError || !unit) {
    return (
      <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
        {query.error instanceof Error ? query.error.message : t("notFound")}
      </Alert>
    );
  }

  const onHand = ON_HAND.has(unit.status);

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <Stack gap="2xs">
          <Group gap="sm">
            <Title order={2} ff="monospace">
              {unit.imei}
            </Title>
            <Badge size="sm" variant="light" color={onHand ? "teal" : "gray"}>
              {tDoc(`deviceStatus.${unit.status}`)}
            </Badge>
            <Badge size="sm" variant="light">
              {tDoc(`condition.${unit.condition}`)}
            </Badge>
          </Group>
          <Text size="sm" c="dimmed">
            <Link href={`/products/${unit.productId}`}>{unit.productName}</Link>
            {" · "}
            {unit.sku}
            {unit.locationId && (
              <>
                {" · "}
                {locations.get(unit.locationId) ?? tCommon("none")}
              </>
            )}
          </Text>
        </Stack>

        <Group gap="sm">
          {unit.status === "in_stock" && can(Permission.Sales.Manage) && (
            <Button onClick={() => setSelling(true)}>{tSell("sellThis")}</Button>
          )}
          {canPrice && onHand && (
            <>
              <Button variant="light" onClick={() => setRepricing(true)}>
                {t("reprice")}
              </Button>
              <Button variant="light" onClick={() => setRegrading(true)}>
                {t("changeCondition")}
              </Button>
            </>
          )}
        </Group>
      </Group>

      {/* FR-2.14: the rule refused, so the screen says so rather than
          showing zero or the catalog price of a used handset. */}
      {unit.resolvedPrice === null && (
        <Alert variant="light" color="yellow" icon={<IconAlertCircle size={18} />}>
          <Text fw={500}>{t("notPriced")}</Text>
          <Text size="sm">{t("notPricedHint")}</Text>
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        <Figure
          label={t("resolvedPrice")}
          value={
            unit.resolvedPrice === null
              ? t("notPriced")
              : `${unit.resolvedPrice} ${unit.currency}`
          }
        />
        <Figure
          label={t("askingPrice")}
          value={
            unit.askingPrice === null
              ? tCommon("none")
              : `${unit.askingPrice} ${unit.currency}`
          }
        />
        {/* Absent without Cost.View — the payload never carried it (FR-1.7). */}
        {unit.acquisitionCost !== undefined && unit.acquisitionCost !== null && (
          <Figure
            label={t("acquisitionCost")}
            value={`${unit.acquisitionCost} ${unit.currency}`}
          />
        )}
        {unit.cashPaid && (
          <Figure
            label={t("cashPaid")}
            value={unit.cashPaid}
            hint={t("cashPaidHint")}
          />
        )}
      </SimpleGrid>

      {(unit.imei2 || unit.serialNumber) && (
        <Card withBorder radius="md" padding="lg">
          <Group gap="xl">
            {unit.imei2 && (
              <Figure label={t("imei2")} value={unit.imei2} mono />
            )}
            {unit.serialNumber && (
              <Figure label={t("serialNumber")} value={unit.serialNumber} mono />
            )}
          </Group>
        </Card>
      )}

      {canPrice && (
        <Card withBorder radius="md" padding="lg">
          <Stack gap="md">
            <Text fw={500}>{t("priceHistory")}</Text>
            {history.isLoading ? (
              <Center p="md">
                <Loader size="sm" />
              </Center>
            ) : (history.data ?? []).length === 0 ? (
              <Text size="sm" c="dimmed">
                {t("priceHistoryEmpty")}
              </Text>
            ) : (
              <TableScrollArea>
                <Table verticalSpacing="sm" miw={480}>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{tDoc("created")}</Table.Th>
                      <Table.Th>{t("askingPrice")}</Table.Th>
                      <Table.Th>{tDoc("reason")}</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {(history.data ?? []).map((change) => (
                      <Table.Tr key={change.id}>
                        <Table.Td>
                          {new Date(change.occurredAt).toLocaleString()}
                        </Table.Td>
                        <Table.Td>
                          {change.oldPrice === null
                            ? t("priceFirst", {
                                price: `${change.newPrice} ${change.currency}`,
                              })
                            : t("priceChanged", {
                                oldPrice: change.oldPrice,
                                newPrice: `${change.newPrice} ${change.currency}`,
                              })}
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm" c="dimmed">
                            {change.reason ?? tCommon("none")}
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </TableScrollArea>
            )}
          </Stack>
        </Card>
      )}

      {repricing && (
        <RepriceModal unit={unit} onClose={() => setRepricing(false)} />
      )}
      {regrading && (
        <ConditionModal unit={unit} onClose={() => setRegrading(false)} />
      )}
      {selling && <SellUnitModal unit={unit} onClose={() => setSelling(false)} />}
    </Stack>
  );
}

/**
 * The counter's shortcut: open an invoice and put this handset on it
 * (FR-4.1, FR-4.2), without going back to the invoice list to do it.
 *
 * The location defaults to the one holding the unit, because a handset
 * scanned onto an invoice raised elsewhere is refused (FR-4.4) — offering
 * any other default would be offering a guaranteed rejection.
 *
 * The two calls are not atomic, and deliberately not hidden behind one: if
 * the scan is refused — the commonest reason being a handset nobody has
 * priced (FR-4.2b) — the draft invoice still exists and the operator lands
 * on it, which is where they would want to be anyway.
 */
function SellUnitModal({
  unit,
  onClose,
}: {
  unit: DeviceUnit;
  onClose: () => void;
}) {
  const tSell = useTranslations("invoices.sell");
  const tInvoices = useTranslations("invoices");
  const tCommon = useTranslations("common");
  const router = useRouter();

  const [locationId, setLocationId] = useState<string | null>(unit.locationId);
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const locations = useResourceList<Location>("locations", {
    page: 1,
    pageSize: 200,
    isActive: true,
  });
  const customers = useResourceList<Customer>("customers", {
    page: 1,
    pageSize: 200,
    isActive: true,
  });

  const start = useMutation({
    mutationFn: async () => {
      const invoice = await apiSend<SalesInvoice>("POST", "/invoices", {
        locationId,
        ...(customerId ? { customerId } : {}),
      });
      await apiSend("POST", `/invoices/${invoice!.id}/scan`, { code: unit.imei });
      return invoice!;
    },
  });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!locationId) return;
    try {
      const invoice = await start.mutateAsync();
      router.push(`/invoices/${invoice.id}`);
    } catch (thrown) {
      setError(errorMessage(thrown, tCommon("retry")));
    }
  }

  return (
    <FormModal
      opened
      onClose={onClose}
      title={tSell("sellThisTitle")}
      onSubmit={submit}
      busy={start.isPending}
      error={error}
      submitLabel={tSell("sellThis")}
    >
      <Text size="sm" c="dimmed">
        {tSell("sellThisBody")}
      </Text>

      {/* Said before the call, not after: the scan will be refused, and the
          Seller reading this cannot fix it themselves (FR-4.2b). */}
      {unit.resolvedPrice === null && (
        <Alert variant="light" color="yellow" icon={<IconAlertCircle size={18} />}>
          {tSell("sellThisUnpriced")}
        </Alert>
      )}

      <Select
        label={tInvoices("location")}
        value={locationId}
        onChange={setLocationId}
        searchable
        required
        data={(locations.data?.items ?? []).map((location) => ({
          value: location.id,
          label: location.name,
        }))}
        data-autofocus
      />
      <Select
        label={tInvoices("customer")}
        placeholder={tInvoices("walkIn")}
        value={customerId}
        onChange={setCustomerId}
        searchable
        clearable
        data={(customers.data?.items ?? []).map((customer) => ({
          value: customer.id,
          label: customer.fullName,
        }))}
      />
    </FormModal>
  );
}

function Figure({
  label,
  value,
  hint,
  mono,
}: {
  label: string;
  value: string;
  hint?: string;
  mono?: boolean;
}) {
  return (
    <Stack gap="3xs">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text fw={600} ff={mono ? "monospace" : undefined}>
        {value}
      </Text>
      {hint && (
        <Text size="xs" c="dimmed">
          {hint}
        </Text>
      )}
    </Stack>
  );
}

/** FR-2.15/FR-2.16: a cut is an append-only row, never an overwrite. */
function RepriceModal({
  unit,
  onClose,
}: {
  unit: DeviceUnit;
  onClose: () => void;
}) {
  const t = useTranslations("deviceUnits");
  const tCommon = useTranslations("common");
  const tDoc = useTranslations("documents");

  const [price, setPrice] = useState(unit.askingPrice ?? "");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reprice = useDocumentAction<
    DeviceUnit,
    { askingPrice: string; reason: string | null }
  >("device-units", unit.id, { method: "PATCH", path: "/price" });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!isValidPriceInput(price, unit.currency)) {
      setError(
        unit.currency === "USD" ? tDoc("priceHintUsd") : tDoc("priceHintUzs"),
      );
      return;
    }
    try {
      await reprice.mutateAsync({
        askingPrice: price.trim(),
        reason: reason.trim() || null,
      });
      notifySuccess(t("repriced"));
      onClose();
    } catch (thrown) {
      setError(errorMessage(thrown, tCommon("retry")));
    }
  }

  return (
    <FormModal
      opened
      onClose={onClose}
      title={t("repriceTitle")}
      onSubmit={submit}
      busy={reprice.isPending}
      error={error}
      submitLabel={tCommon("save")}
    >
      <TextInput
        label={t("newPrice")}
        description={t("repriceHint")}
        value={price}
        onChange={(event) => setPrice(event.currentTarget.value)}
        rightSection={
          <Text size="xs" c="dimmed">
            {unit.currency}
          </Text>
        }
        rightSectionWidth={44}
        data-autofocus
      />
      <Textarea
        label={tDoc("reason")}
        value={reason}
        onChange={(event) => setReason(event.currentTarget.value)}
        autosize
        minRows={2}
      />
    </FormModal>
  );
}

/** FR-2.18: condition is a pricing input, so changing it is a pricing act. */
function ConditionModal({
  unit,
  onClose,
}: {
  unit: DeviceUnit;
  onClose: () => void;
}) {
  const t = useTranslations("deviceUnits");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");

  const [condition, setCondition] = useState<DeviceCondition>(unit.condition);
  const [error, setError] = useState<string | null>(null);

  const change = useDocumentAction<DeviceUnit, { condition: DeviceCondition }>(
    "device-units",
    unit.id,
    { method: "PATCH", path: "/condition" },
  );

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await change.mutateAsync({ condition });
      notifySuccess(t("conditionChanged"));
      onClose();
    } catch (thrown) {
      setError(errorMessage(thrown, tCommon("retry")));
    }
  }

  return (
    <FormModal
      opened
      onClose={onClose}
      title={t("changeConditionTitle")}
      onSubmit={submit}
      busy={change.isPending}
      error={error}
      submitLabel={tCommon("save")}
    >
      <Select
        label={t("condition")}
        description={t("changeConditionHint")}
        value={condition}
        onChange={(value) => setCondition((value ?? unit.condition) as DeviceCondition)}
        data={CONDITIONS.map((value) => ({
          value,
          label: tDoc(`condition.${value}`),
        }))}
        allowDeselect={false}
      />
    </FormModal>
  );
}
