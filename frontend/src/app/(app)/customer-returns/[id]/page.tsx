"use client";

import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ConfirmReturnModal } from "@/app/(app)/customer-returns/ConfirmReturnModal";
import { CustomerReturnLines } from "@/app/(app)/customer-returns/CustomerReturnLines";
import { RefundModal } from "@/app/(app)/customer-returns/RefundModal";
import { DetailError, DetailLoading } from "@/components/DetailStates";
import { DocumentStatusBadge } from "@/components/DocumentStatusBadge";
import { ErrorAlert } from "@/components/ErrorAlert";
import { useCan } from "@/components/MeProvider";
import { ReasonModal } from "@/components/ReasonModal";
import { ScanConsole } from "@/components/scan/ScanConsole";
import { Subtotals } from "@/components/Subtotals";
import { useCancelDocument } from "@/hooks/use-cancel-document";
import { useDateFormat } from "@/hooks/use-date-format";
import { useDocumentAction } from "@/hooks/use-document";
import { useCustomerLookup, useLocationLookup } from "@/hooks/use-lookup";
import { useResourceItem } from "@/hooks/use-resource";
import {
  canConfirmReturn,
  CUSTOMER_RETURN_REASON_COLOR,
  keptSubtotals,
} from "@/lib/customer-returns";
import { isEditable } from "@/lib/documents";
import { formatMoney } from "@/lib/money";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { CustomerReturn, CustomerReturnLine, SalesInvoice } from "@/lib/types";

export default function CustomerReturnPage() {
  const t = useTranslations("customerReturns");
  const tScan = useTranslations("customerReturns.scan");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { formatDateTime } = useDateFormat();
  const { id } = useParams<{ id: string }>();
  const can = useCan();
  const queryClient = useQueryClient();

  const query = useResourceItem<CustomerReturn>("customer-returns", id);
  const customers = useCustomerLookup();
  const locations = useLocationLookup();

  const [confirming, setConfirming] = useState(false);
  const [editingLine, setEditingLine] = useState<CustomerReturnLine | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmRefusal, setConfirmRefusal] = useState<string | null>(null);

  const document = query.data;

  // Only to show what is still owed, so the confirm modal can offer it as
  // the relief. The server re-reads and re-caps it regardless.
  const sale = useResourceItem<SalesInvoice>(
    "invoices",
    document?.salesInvoiceId ?? "",
  );

  const confirm = useDocumentAction<CustomerReturn, { debtRelief?: string }>(
    "customer-returns",
    id,
    { path: "/confirm" },
  );
  const cancelDoc = useCancelDocument("customer-returns", id, setActionError);
  const unscan = useDocumentAction<null, { imei: string }>("customer-returns", id, {
    method: "DELETE",
    path: (payload) => `/scan/${payload.imei}`,
  });

  /**
   * A scan answers with the whole refreshed document, so the cache takes it
   * directly instead of refetching — a round trip between beeps is exactly
   * what §6 budgets against.
   */
  function applyScan(updated: CustomerReturn) {
    queryClient.setQueryData<CustomerReturn>(
      ["customer-returns", "item", id],
      updated,
    );
  }

  if (query.isLoading) return <DetailLoading />;

  if (query.isError || !document) {
    return (
      <DetailError
        message={query.error instanceof Error ? query.error.message : t("notFound")}
      />
    );
  }

  const draft = isEditable(document.status);
  const canManage = can(Permission.CustomerReturn.Manage);
  const ready = canConfirmReturn(document);
  const kept = keptSubtotals(document);
  const outstanding =
    sale.data && sale.data.paymentType === "store_credit"
      ? sale.data.remaining.minor
      : null;

  async function runConfirm(debtRelief: string | null) {
    setActionError(null);
    setConfirmRefusal(null);
    try {
      await confirm.mutateAsync(
        debtRelief === null ? {} : { debtRelief },
      );
      notifySuccess(tDoc("confirmed"));
      setConfirming(false);
    } catch (error) {
      // The refusal names the handset and its actual status, or the balance
      // the relief overshot, so it belongs on the page rather than in a
      // toast that vanishes.
      setConfirming(false);
      setConfirmRefusal(errorMessage(error, tCommon("retry")));
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
            <Title order={2}>{document.number}</Title>
            <DocumentStatusBadge status={document.status} />
            <Badge
              size="sm"
              variant="light"
              color={CUSTOMER_RETURN_REASON_COLOR[document.reason]}
            >
              {t(`reason.${document.reason}`)}
            </Badge>
          </Group>
          <Text size="sm" c="dimmed">
            {document.customerId === null
              ? t("walkIn")
              : (customers.get(document.customerId) ?? tCommon("none"))}
            {" · "}
            {t("invoice")}:{" "}
            <Anchor
              component={Link}
              href={`/invoices/${document.salesInvoiceId}`}
              size="sm"
            >
              {sale.data?.number ?? tCommon("none")}
            </Anchor>
            {" · "}
            {t("location")}: {locations.get(document.locationId) ?? tCommon("none")}
            {" · "}
            {tDoc("created")}: {formatDateTime(document.createdAt)}
          </Text>
          {document.note && <Text size="sm">{document.note}</Text>}
        </Stack>

        <Group gap="sm">
          {draft && canManage && (
            <Button disabled={!ready} onClick={() => setConfirming(true)}>
              {tDoc("confirmAction")}
            </Button>
          )}
          {document.status === "confirmed" && can(Permission.Document.Cancel) && (
            <Button color="red" variant="light" onClick={cancelDoc.open}>
              {tDoc("cancelAction")}
            </Button>
          )}
        </Group>
      </Group>

      {document.status === "cancelled" && (
        <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
          {tDoc("cancelledNotice")}
        </Alert>
      )}

      <ErrorAlert message={actionError} />
      <ErrorAlert message={confirmRefusal} />

      {draft && !ready && (
        <Alert variant="light" color="yellow" icon={<IconAlertCircle size={18} />}>
          {t("emptyBlocker")}
        </Alert>
      )}

      {draft && canManage && (
        <ScanConsole
          resource="customer-returns"
          namespace="customerReturns.scan"
          document={document}
          onScanned={applyScan}
        />
      )}

      <Card withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Text fw={500}>{tDoc("lines")}</Text>
          <CustomerReturnLines
            lines={document.lines}
            emptyMessage={tScan("empty")}
            onRemove={draft && canManage ? removeUnit : undefined}
            onEditRefund={
              draft && can(Permission.Pricing.Override) ? setEditingLine : undefined
            }
            removeLabel={tScan("unscan")}
            editLabel={t("refundTitle")}
            removing={unscan.isPending}
          />

          <Group justify="flex-end" gap="xl" wrap="wrap">
            {kept.length > 0 && (
              <Stack gap="2xs" align="flex-end">
                <Text size="sm" c="dimmed">
                  {t("kept")}
                </Text>
                <Subtotals subtotals={kept} />
              </Stack>
            )}
            <Stack gap="2xs" align="flex-end">
              <Text size="sm" c="dimmed">
                {t("refunded")}
              </Text>
              <Subtotals subtotals={document.subtotals} size="md" fw={600} />
            </Stack>
          </Group>
        </Stack>
      </Card>

      {document.debtRelief !== null && (
        <Alert variant="light" color="blue" icon={<IconAlertCircle size={18} />}>
          {t("debtRelieved", {
            amount: formatMoney(document.debtRelief),
          })}
        </Alert>
      )}

      {!draft && (
        <Text size="sm" c="dimmed">
          {tDoc("immutable")}
        </Text>
      )}

      {editingLine && (
        <RefundModal
          returnId={id}
          line={editingLine}
          onClose={() => setEditingLine(null)}
        />
      )}

      {confirming && (
        <ConfirmReturnModal
          document={document}
          outstandingMinor={outstanding}
          onClose={() => setConfirming(false)}
          onSubmit={runConfirm}
          busy={confirm.isPending}
          error={actionError}
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
