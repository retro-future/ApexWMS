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
  NumberInput,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { IconAlertCircle, IconFileText, IconTrash } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ConfirmSaleModal } from "@/app/(app)/invoices/ConfirmSaleModal";
import { CreditPanel } from "@/app/(app)/invoices/CreditPanel";
import { SellConsole } from "@/app/(app)/invoices/SellConsole";
import { DocumentStatusBadge } from "@/components/DocumentStatusBadge";
import { FormModal } from "@/components/FormModal";
import { useCan } from "@/components/MeProvider";
import { ReasonModal } from "@/components/ReasonModal";
import { Subtotals } from "@/components/Subtotals";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useDocumentAction } from "@/hooks/use-document";
import { useInvoiceQuote } from "@/hooks/use-invoice-quote";
import {
  useCreditCompanyLookup,
  useCustomerLookup,
  useEmployeeLookup,
  useLocationLookup,
  useProductLookup,
} from "@/hooks/use-lookup";
import { useResourceItem } from "@/hooks/use-resource";
import { isEditable } from "@/lib/documents";
import { confirmBlockers, isSerial, quoteSubtotals, type QuoteMap } from "@/lib/invoices";
import { formatMoney } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { InvoiceScanResult, SalesInvoice, SalesInvoiceLine } from "@/lib/types";

export default function InvoicePage() {
  const t = useTranslations("invoices");
  const tSell = useTranslations("invoices.sell");
  const tCredit = useTranslations("credit");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { id } = useParams<{ id: string }>();
  const can = useCan();
  const queryClient = useQueryClient();

  const query = useResourceItem<SalesInvoice>("invoices", id);
  const products = useProductLookup();
  const customers = useCustomerLookup();
  const locations = useLocationLookup();
  const employees = useEmployeeLookup();
  const creditCompanies = useCreditCompanyLookup();
  const { quotes } = useInvoiceQuote(query.data);

  const [overriding, setOverriding] = useState<SalesInvoiceLine | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmRefusal, setConfirmRefusal] = useState<string | null>(null);

  const confirm = useDocumentAction<SalesInvoice, Record<string, unknown>>(
    "invoices",
    id,
    { path: "/confirm" },
  );
  const cancel = useDocumentAction<SalesInvoice, { reason: string | null }>(
    "invoices",
    id,
    { path: "/cancel" },
  );

  /**
   * A scan patches the cached document instead of refetching it: the scan
   * response already carries the line and the running count, and a round
   * trip between beeps is exactly what §6 budgets against.
   */
  function applyScan(result: InvoiceScanResult) {
    queryClient.setQueryData<SalesInvoice>(["invoices", "item", id], (current) => {
      if (!current) return current;
      // Replaces on an accessory re-scan (its quantity went up) and appends
      // on a new line — the one shape covers both.
      const known = current.lines.some((line) => line.id === result.line.id);
      return {
        ...current,
        lines: known
          ? current.lines.map((line) => (line.id === result.line.id ? result.line : line))
          : [...current.lines, result.line],
      };
    });
  }

  if (query.isLoading) {
    return (
      <Center p="xl">
        <Loader size="sm" />
      </Center>
    );
  }

  const invoice = query.data;
  if (query.isError || !invoice) {
    return (
      <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
        {query.error instanceof Error ? query.error.message : t("notFound")}
      </Alert>
    );
  }

  const draft = isEditable(invoice.status);
  const blockers = confirmBlockers(invoice, quotes);
  // A draft holds no prices, so its total is assembled here and labelled a
  // quote. A confirmed invoice reports the server's own snapshot.
  const subtotals = draft ? quoteSubtotals(invoice, quotes) : invoice.subtotals;

  async function runConfirm(terms: Record<string, unknown>) {
    setActionError(null);
    setConfirmRefusal(null);
    try {
      await confirm.mutateAsync(terms);
      notifySuccess(tDoc("confirmed"));
      setConfirming(false);
    } catch (error) {
      // FR-4.5b2 and FR-4.7 name the offending line, so the refusal is a
      // worklist and belongs on the page, not in a toast that vanishes.
      setConfirming(false);
      setConfirmRefusal(errorMessage(error, tCommon("retry")));
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

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <Stack gap="2xs">
          <Group gap="sm">
            <Title order={2}>{invoice.number}</Title>
            <DocumentStatusBadge status={invoice.status} />
            {invoice.paymentType !== "paid_in_full" && (
              <Badge variant="light" color="grape">
                {tCredit(
                  invoice.paymentType === "store_credit"
                    ? "storeCredit"
                    : "creditCompany",
                )}
              </Badge>
            )}
          </Group>
          <Text size="sm" c="dimmed">
            {customers.get(invoice.customerId) ?? t("walkIn")}
            {" · "}
            {t("location")}: {locations.get(invoice.locationId) ?? tCommon("none")}
            {" · "}
            {tDoc("created")}: {new Date(invoice.createdAt).toLocaleString()}
          </Text>
          {invoice.confirmedAt && (
            <Text size="sm" c="dimmed">
              {tDoc("confirmed")}: {new Date(invoice.confirmedAt).toLocaleString()}
              {employees.get(invoice.confirmedBy) &&
                ` · ${employees.get(invoice.confirmedBy)}`}
            </Text>
          )}
          {invoice.note && <Text size="sm">{invoice.note}</Text>}
        </Stack>

        <Group gap="sm">
          {draft && can(Permission.Sales.Manage) && (
            <Button onClick={() => setConfirming(true)}>{tDoc("confirmAction")}</Button>
          )}
          {/* A draft holds no prices to print, and the server refuses it. */}
          {!draft && (
            <Button
              component="a"
              href={`/api/backend/invoices/${invoice.id}/pdf`}
              target="_blank"
              rel="noreferrer"
              variant="light"
              leftSection={<IconFileText size={16} />}
            >
              {tDoc("openPdf")}
            </Button>
          )}
          {invoice.status === "confirmed" && can(Permission.Document.Cancel) && (
            <Button color="red" variant="light" onClick={() => setCancelling(true)}>
              {tDoc("cancelAction")}
            </Button>
          )}
        </Group>
      </Group>

      {invoice.status === "cancelled" && (
        <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
          {tDoc("cancelledNotice")}
          {invoice.cancellationReason && ` — ${invoice.cancellationReason}`}
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
              {blockers.isEmpty && <List.Item>{t("blockerEmpty")}</List.Item>}
              {blockers.unresolvedLines.map((line) => (
                <List.Item key={line.id}>
                  {t("blockerUnpriced", {
                    product: products.get(line.productId) ?? tCommon("none"),
                  })}
                </List.Item>
              ))}
            </List>
          </Stack>
        </Alert>
      )}

      {draft && can(Permission.Sales.Manage) && (
        <SellConsole invoice={invoice} onScanned={applyScan} />
      )}

      <Card withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Text fw={500}>{tDoc("lines")}</Text>

          {invoice.lines.length === 0 ? (
            <Text size="sm" c="dimmed">
              {tSell("empty")}
            </Text>
          ) : (
            <TableScrollArea>
              <Table verticalSpacing="sm" miw={780}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{tDoc("product")}</Table.Th>
                    <Table.Th>{tDoc("quantity")}</Table.Th>
                    <Table.Th>{tDoc("resolvedPrice")}</Table.Th>
                    <Table.Th>{draft ? tDoc("quote") : tDoc("chargedPrice")}</Table.Th>
                    <Table.Th />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {invoice.lines.map((line) => (
                    <LineRow
                      key={line.id}
                      line={line}
                      draft={draft}
                      quotes={quotes}
                      productName={products.get(line.productId)}
                      approver={employees.get(line.priceApprovedBy)}
                      invoiceId={invoice.id}
                      onOverride={() => setOverriding(line)}
                      onError={setActionError}
                    />
                  ))}
                </Table.Tbody>
              </Table>
            </TableScrollArea>
          )}

          {subtotals.length > 0 && (
            <Group justify="space-between" wrap="wrap">
              <Text size="sm" c="dimmed">
                {draft ? tDoc("quoteHint") : tDoc("subtotalsHint")}
              </Text>
              <Subtotals subtotals={subtotals} size="md" fw={600} />
            </Group>
          )}
        </Stack>
      </Card>

      {/* A financed sale shows nothing here on purpose: the company paid the
          store in full at confirm, so there is no balance to display and
          attributing one to the customer would be a lie (§4.7). */}
      {invoice.paymentType === "store_credit" && !draft && (
        <CreditPanel invoice={invoice} />
      )}

      {invoice.paymentType === "credit_company" && !draft && (
        <Text size="sm" c="dimmed">
          {tCredit("financedNotice", {
            company: creditCompanies.get(invoice.creditCompanyId) ?? tCommon("none"),
          })}
          {invoice.contractRef && ` · ${invoice.contractRef}`}
        </Text>
      )}

      {!draft && (
        <Text size="sm" c="dimmed">
          {tDoc("immutable")}
        </Text>
      )}

      {overriding && (
        <OverridePriceModal
          invoiceId={invoice.id}
          line={overriding}
          resolvedMinor={quotes.get(overriding.id)?.resolvedMinor ?? null}
          onClose={() => setOverriding(null)}
        />
      )}

      {confirming && (
        <ConfirmSaleModal
          invoice={invoice}
          quote={subtotals}
          busy={confirm.isPending}
          error={actionError}
          onClose={() => setConfirming(false)}
          onSubmit={runConfirm}
        />
      )}

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

/**
 * One line, in both of the states it can be read in: a draft showing the
 * quote this screen assembled, and a confirmed invoice showing the snapshot
 * the server took at confirm (FR-4.5b).
 */
function LineRow({
  line,
  invoiceId,
  draft,
  quotes,
  productName,
  approver,
  onOverride,
  onError,
}: {
  line: SalesInvoiceLine;
  invoiceId: string;
  draft: boolean;
  quotes: QuoteMap;
  productName: string | undefined;
  approver: string | undefined;
  onOverride: () => void;
  onError: (message: string) => void;
}) {
  const t = useTranslations("invoices");
  const tSell = useTranslations("invoices.sell");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const can = useCan();

  // Both close over this line, so the id stays in the URL where it belongs
  // rather than riding along in a body the endpoint does not declare.
  const remove = useDocumentAction<SalesInvoice>("invoices", invoiceId, {
    method: "DELETE",
    path: `/lines/${line.id}`,
  });
  const requantify = useDocumentAction<SalesInvoice, { quantity: number }>(
    "invoices",
    invoiceId,
    { method: "PATCH", path: `/lines/${line.id}` },
  );
  const busy = remove.isPending || requantify.isPending;

  async function run(action: Promise<unknown>, done?: () => void) {
    try {
      await action;
      done?.();
    } catch (error) {
      onError(errorMessage(error, tCommon("retry")));
    }
  }

  const quote = quotes.get(line.id);
  const resolvedMinor = draft ? (quote?.resolvedMinor ?? null) : line.resolvedPriceMinor;
  const charged = draft ? (quote?.chargedMinor ?? null) : line.chargedPriceMinor;
  const deviates = draft
    ? line.overridePriceMinor !== null && line.overridePriceMinor !== resolvedMinor
    : line.isDeviation;

  return (
    <Table.Tr>
      <Table.Td>
        <Stack gap="3xs">
          <Text size="sm">{productName ?? tCommon("none")}</Text>
          {!isSerial(line) && (
            <Text size="xs" c="dimmed">
              {tSell("accessory")}
            </Text>
          )}
        </Stack>
      </Table.Td>
      <Table.Td>
        {draft && !isSerial(line) && can(Permission.Sales.Manage) ? (
          <NumberInput
            value={line.quantity}
            onChange={(value) => run(requantify.mutateAsync({ quantity: Number(value) || 1 }))}
            min={1}
            allowDecimal={false}
            disabled={busy}
            w={90}
            aria-label={tDoc("quantity")}
          />
        ) : (
          line.quantity
        )}
      </Table.Td>
      <Table.Td>
        {resolvedMinor === null ? (
          <Badge size="xs" variant="light" color="yellow">
            {tSell("needsPrice")}
          </Badge>
        ) : (
          <Text
            size="sm"
            td={deviates ? "line-through" : undefined}
            c={deviates ? "dimmed" : undefined}
          >
            {formatMoney(resolvedMinor, line.currency)}
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        {charged === null ? (
          tCommon("none")
        ) : (
          <Stack gap="3xs">
            <Text size="sm" fw={deviates ? 600 : undefined}>
              {formatMoney(charged, line.currency)}
            </Text>
            {deviates && (
              <Text size="xs" c="dimmed">
                {/* FR-4.5f: the approver is whoever overrode it, which need
                    not be whoever confirmed the invoice. */}
                {approver ? tDoc("approvedBy", { name: approver }) : t("approvedBySomeone")}
                {line.priceNote && ` — ${line.priceNote}`}
              </Text>
            )}
          </Stack>
        )}
      </Table.Td>
      <Table.Td>
        <Group gap="2xs" justify="flex-end" wrap="nowrap">
          {draft && can(Permission.Pricing.Override) && (
            <Button size="compact-sm" variant="subtle" onClick={onOverride}>
              {tSell("override")}
            </Button>
          )}
          {draft && can(Permission.Sales.Manage) && (
            <ActionIcon
              variant="subtle"
              color="red"
              aria-label={tSell("remove")}
              loading={busy}
              onClick={() => run(remove.mutateAsync(undefined as never), () => notifySuccess(tSell("removed")))}
            >
              <IconTrash size={16} />
            </ActionIcon>
          )}
        </Group>
      </Table.Td>
    </Table.Tr>
  );
}

/**
 * FR-4.5: an Owner or Manager charges something other than what the system
 * resolved, and the override is stamped with their name there and then.
 *
 * `price` and `note` always travel together. The server branches on which
 * keys arrived and then reads `price`, so a body carrying only a note would
 * clear the override — the two are one decision, not two fields.
 *
 * Clearing is its own action because it is not the same as pricing at zero:
 * it hands the line back to resolution, and drops the approver and the note
 * with it.
 */
function OverridePriceModal({
  invoiceId,
  line,
  resolvedMinor,
  onClose,
}: {
  invoiceId: string;
  line: SalesInvoiceLine;
  resolvedMinor: number | null;
  onClose: () => void;
}) {
  const tSell = useTranslations("invoices.sell");
  const tCommon = useTranslations("common");

  const [price, setPrice] = useState(line.overridePrice ?? "");
  const [note, setNote] = useState(line.priceNote ?? "");
  const [error, setError] = useState<string | null>(null);

  const override = useDocumentAction<
    SalesInvoice,
    { price: string | null; note: string | null }
  >("invoices", invoiceId, {
    method: "PATCH",
    path: () => `/lines/${line.id}`,
  });

  async function send(body: { price: string | null; note: string | null }) {
    setError(null);
    try {
      await override.mutateAsync(body);
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
      title={tSell("overrideTitle")}
      onSubmit={(event) => {
        event.preventDefault();
        send({ price: price.trim() || null, note: note.trim() || null });
      }}
      busy={override.isPending}
      error={error}
      submitLabel={tCommon("save")}
    >
      <TextInput
        label={tSell("overridePrice")}
        description={
          resolvedMinor === null
            ? tSell("noResolvedPrice")
            : tSell("resolvedHint", {
                price: formatMoney(resolvedMinor, line.currency),
              })
        }
        value={price}
        onChange={(event) => setPrice(event.currentTarget.value)}
        rightSection={
          <Text size="xs" c="dimmed">
            {line.currency}
          </Text>
        }
        rightSectionWidth={44}
        data-autofocus
      />
      <Textarea
        label={tSell("overrideNote")}
        description={tSell("overrideNoteHint")}
        value={note}
        onChange={(event) => setNote(event.currentTarget.value)}
        autosize
        minRows={2}
      />
      {line.overridePriceMinor !== null && (
        <Button
          variant="subtle"
          color="red"
          loading={override.isPending}
          onClick={() => send({ price: null, note: null })}
        >
          {tSell("clearOverride")}
        </Button>
      )}
    </FormModal>
  );
}
