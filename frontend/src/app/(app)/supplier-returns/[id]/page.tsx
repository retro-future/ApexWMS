"use client";

import {
  Alert,
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
import { useParams } from "next/navigation";
import { useState } from "react";

import { DetailError, DetailLoading } from "@/components/DetailStates";
import { DocumentStatusBadge } from "@/components/DocumentStatusBadge";
import { ErrorAlert } from "@/components/ErrorAlert";
import { useCan } from "@/components/MeProvider";
import { OpenPdfButton } from "@/components/OpenPdfButton";
import { ReasonModal } from "@/components/ReasonModal";
import { RemovalLinesTable } from "@/components/RemovalLinesTable";
import { ScanConsole } from "@/components/scan/ScanConsole";
import { useCancelDocument } from "@/hooks/use-cancel-document";
import { useDateFormat } from "@/hooks/use-date-format";
import { useDocumentAction } from "@/hooks/use-document";
import { useLocationLookup, useSupplierLookup } from "@/hooks/use-lookup";
import { useResourceItem } from "@/hooks/use-resource";
import { isEditable } from "@/lib/documents";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import { canConfirmRemoval, SUPPLIER_RETURN_REASON_COLOR } from "@/lib/removals";
import type { SupplierReturn } from "@/lib/types";

export default function SupplierReturnPage() {
  const t = useTranslations("supplierReturns");
  const tScan = useTranslations("supplierReturns.scan");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { formatDateTime } = useDateFormat();
  const { id } = useParams<{ id: string }>();
  const can = useCan();
  const queryClient = useQueryClient();

  const query = useResourceItem<SupplierReturn>("supplier-returns", id);
  const suppliers = useSupplierLookup();
  const locations = useLocationLookup();

  const [confirming, setConfirming] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmRefusal, setConfirmRefusal] = useState<string | null>(null);

  const confirm = useDocumentAction<SupplierReturn>("supplier-returns", id, {
    path: "/confirm",
  });
  const cancelDoc = useCancelDocument("supplier-returns", id, setActionError);
  const unscan = useDocumentAction<null, { imei: string }>("supplier-returns", id, {
    method: "DELETE",
    path: (payload) => `/scan/${payload.imei}`,
  });

  /**
   * A scan answers with the whole refreshed document, so the cache takes it
   * directly instead of refetching — a round trip between beeps is exactly
   * what §6 budgets against.
   */
  function applyScan(updated: SupplierReturn) {
    queryClient.setQueryData<SupplierReturn>(
      ["supplier-returns", "item", id],
      updated,
    );
  }

  if (query.isLoading) return <DetailLoading />;

  const supplierReturn = query.data;
  if (query.isError || !supplierReturn) {
    return (
      <DetailError
        message={query.error instanceof Error ? query.error.message : t("notFound")}
      />
    );
  }

  const draft = isEditable(supplierReturn.status);
  const canManage = can(Permission.SupplierReturn.Manage);
  const ready = canConfirmRemoval(supplierReturn);

  async function runConfirm() {
    setActionError(null);
    setConfirmRefusal(null);
    try {
      await confirm.mutateAsync(undefined as never);
      notifySuccess(tDoc("confirmed"));
      setConfirming(false);
    } catch (error) {
      // The refusal names the handset and its actual status (FR-5.2), so it
      // belongs on the page rather than in a toast that vanishes.
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
            <Title order={2}>{supplierReturn.number}</Title>
            <DocumentStatusBadge status={supplierReturn.status} />
            <Badge
              size="sm"
              variant="light"
              color={SUPPLIER_RETURN_REASON_COLOR[supplierReturn.reason]}
            >
              {tDoc(`returnReason.${supplierReturn.reason}`)}
            </Badge>
          </Group>
          <Text size="sm" c="dimmed">
            {suppliers.get(supplierReturn.supplierId) ?? tCommon("none")}
            {" · "}
            {t("location")}:{" "}
            {locations.get(supplierReturn.locationId) ?? tCommon("none")}
            {" · "}
            {tDoc("created")}: {formatDateTime(supplierReturn.createdAt)}
          </Text>
          {supplierReturn.note && <Text size="sm">{supplierReturn.note}</Text>}
        </Stack>

        <Group gap="sm">
          {draft && canManage && (
            <Button disabled={!ready} onClick={() => setConfirming(true)}>
              {tDoc("confirmAction")}
            </Button>
          )}
          {/* Nothing has left the shelf while it is a draft, and the server
              refuses it. No cost gate: this note carries no money. */}
          {!draft && (
            <OpenPdfButton
              href={`/api/backend/supplier-returns/${supplierReturn.id}/pdf`}
            />
          )}
          {supplierReturn.status === "confirmed" &&
            can(Permission.Document.Cancel) && (
              <Button color="red" variant="light" onClick={cancelDoc.open}>
                {tDoc("cancelAction")}
              </Button>
            )}
        </Group>
      </Group>

      {supplierReturn.status === "cancelled" && (
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
          namespace="supplierReturns.scan"
          resource="supplier-returns"
          document={supplierReturn}
          onScanned={applyScan}
        />
      )}

      <Card withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Text fw={500}>{tDoc("lines")}</Text>
          <RemovalLinesTable
            lines={supplierReturn.lines}
            emptyMessage={tScan("empty")}
            onRemove={draft && canManage ? removeUnit : undefined}
            removeLabel={tScan("unscan")}
            removing={unscan.isPending}
          />
        </Stack>
      </Card>

      {!draft && (
        <Text size="sm" c="dimmed">
          {tDoc("immutable")}
        </Text>
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
