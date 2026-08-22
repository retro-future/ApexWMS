"use client";

import { Alert, Badge, Button, Card, Group, List, Stack, Table, Text, Title } from "@mantine/core";
import { IconAlertCircle, IconFileText } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ConfirmSaleModal } from "@/app/(app)/invoices/ConfirmSaleModal";
import { CreditPanel } from "@/app/(app)/invoices/CreditPanel";
import { InvoiceLineRow } from "@/app/(app)/invoices/InvoiceLineRow";
import { OverridePriceModal } from "@/app/(app)/invoices/OverridePriceModal";
import { SellConsole } from "@/app/(app)/invoices/SellConsole";
import { DetailError, DetailLoading } from "@/components/DetailStates";
import { DocumentStatusBadge } from "@/components/DocumentStatusBadge";
import { useCan } from "@/components/MeProvider";
import { ReasonModal } from "@/components/ReasonModal";
import { Subtotals } from "@/components/Subtotals";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useCancelDocument } from "@/hooks/use-cancel-document";
import { useDateFormat } from "@/hooks/use-date-format";
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
import { confirmBlockers, quoteSubtotals } from "@/lib/invoices";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { InvoiceScanResult, SalesInvoice, SalesInvoiceLine } from "@/lib/types";

export default function InvoicePage() {
  const t = useTranslations("invoices");
  const tSell = useTranslations("invoices.sell");
  const tCredit = useTranslations("credit");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { formatDateTime } = useDateFormat();
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
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmRefusal, setConfirmRefusal] = useState<string | null>(null);

  const confirm = useDocumentAction<SalesInvoice, Record<string, unknown>>(
    "invoices",
    id,
    { path: "/confirm" },
  );
  const cancelDoc = useCancelDocument("invoices", id, setActionError);

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

  if (query.isLoading) return <DetailLoading />;

  const invoice = query.data;
  if (query.isError || !invoice) {
    return (
      <DetailError
        message={query.error instanceof Error ? query.error.message : t("notFound")}
      />
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
            {tDoc("created")}: {formatDateTime(invoice.createdAt)}
          </Text>
          {invoice.confirmedAt && (
            <Text size="sm" c="dimmed">
              {tDoc("confirmed")}: {formatDateTime(invoice.confirmedAt)}
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
            <Button color="red" variant="light" onClick={cancelDoc.open}>
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
                    <InvoiceLineRow
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
        opened={cancelDoc.opened}
        onClose={cancelDoc.close}
        title={t("cancelTitle")}
        description={t("cancelBody")}
        submitLabel={tDoc("cancelAction")}
        color="red"
        busy={cancelDoc.busy}
        error={actionError}
        onSubmit={cancelDoc.run}
      />
    </Stack>
  );
}
