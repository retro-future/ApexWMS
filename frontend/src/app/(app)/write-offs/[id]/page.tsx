"use client";

import { Alert, Badge, Button, Card, Group, Stack, Text, Title } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useState } from "react";

import { DetailError, DetailLoading } from "@/components/DetailStates";
import { DocumentStatusBadge } from "@/components/DocumentStatusBadge";
import { ErrorAlert } from "@/components/ErrorAlert";
import { useCan } from "@/components/MeProvider";
import { ReasonModal } from "@/components/ReasonModal";
import { RemovalLinesTable } from "@/components/RemovalLinesTable";
import { ScanConsole } from "@/components/scan/ScanConsole";
import { useCancelDocument } from "@/hooks/use-cancel-document";
import { useDateFormat } from "@/hooks/use-date-format";
import { useDocumentAction } from "@/hooks/use-document";
import { useLocationLookup } from "@/hooks/use-lookup";
import { useResourceItem } from "@/hooks/use-resource";
import { isEditable } from "@/lib/documents";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import { canConfirmRemoval, WRITE_OFF_REASON_COLOR } from "@/lib/removals";
import type { WriteOff } from "@/lib/types";

export default function WriteOffPage() {
  const t = useTranslations("writeOffs");
  const tScan = useTranslations("writeOffs.scan");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { formatDateTime } = useDateFormat();
  const { id } = useParams<{ id: string }>();
  const can = useCan();
  const queryClient = useQueryClient();

  const query = useResourceItem<WriteOff>("write-offs", id);
  const locations = useLocationLookup();

  const [confirming, setConfirming] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmRefusal, setConfirmRefusal] = useState<string | null>(null);

  const confirm = useDocumentAction<WriteOff>("write-offs", id, { path: "/confirm" });
  const cancelDoc = useCancelDocument("write-offs", id, setActionError);
  const unscan = useDocumentAction<null, { imei: string }>("write-offs", id, {
    method: "DELETE",
    path: (payload) => `/scan/${payload.imei}`,
  });

  function applyScan(updated: WriteOff) {
    queryClient.setQueryData<WriteOff>(["write-offs", "item", id], updated);
  }

  if (query.isLoading) return <DetailLoading />;

  const writeOff = query.data;
  if (query.isError || !writeOff) {
    return (
      <DetailError
        message={query.error instanceof Error ? query.error.message : t("notFound")}
      />
    );
  }

  const draft = isEditable(writeOff.status);
  const canManage = can(Permission.WriteOff.Manage);
  const ready = canConfirmRemoval(writeOff);

  async function runConfirm() {
    setActionError(null);
    setConfirmRefusal(null);
    try {
      await confirm.mutateAsync(undefined as never);
      notifySuccess(tDoc("confirmed"));
      setConfirming(false);
    } catch (error) {
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
            <Title order={2}>{writeOff.number}</Title>
            <DocumentStatusBadge status={writeOff.status} />
            <Badge
              size="sm"
              variant="light"
              color={WRITE_OFF_REASON_COLOR[writeOff.reason]}
            >
              {tDoc(`writeOffReason.${writeOff.reason}`)}
            </Badge>
          </Group>
          <Text size="sm" c="dimmed">
            {t("location")}: {locations.get(writeOff.locationId) ?? tCommon("none")}
            {" · "}
            {tDoc("created")}: {formatDateTime(writeOff.createdAt)}
          </Text>
          {writeOff.note && <Text size="sm">{writeOff.note}</Text>}
        </Stack>

        <Group gap="sm">
          {draft && canManage && (
            <Button disabled={!ready} onClick={() => setConfirming(true)}>
              {tDoc("confirmAction")}
            </Button>
          )}
          {writeOff.status === "confirmed" && can(Permission.Document.Cancel) && (
            <Button color="red" variant="light" onClick={cancelDoc.open}>
              {tDoc("cancelAction")}
            </Button>
          )}
        </Group>
      </Group>

      {writeOff.status === "cancelled" && (
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
          namespace="writeOffs.scan"
          resource="write-offs"
          document={writeOff}
          onScanned={applyScan}
        />
      )}

      <Card withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Text fw={500}>{tDoc("lines")}</Text>
          <RemovalLinesTable
            lines={writeOff.lines}
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
