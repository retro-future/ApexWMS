"use client";

import { Alert, Button, Card, Group, Stack, Text, Title } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useState } from "react";

import { CountLineTable } from "@/app/(app)/stock-counts/CountLineTable";
import { CountScanConsole } from "@/app/(app)/stock-counts/CountScanConsole";
import { CountStepBadge } from "@/app/(app)/stock-counts/CountStepBadge";
import { DiscrepancyReport } from "@/app/(app)/stock-counts/DiscrepancyReport";
import { SurplusWorklist } from "@/app/(app)/stock-counts/SurplusWorklist";
import { DetailError, DetailLoading } from "@/components/DetailStates";
import { ErrorAlert } from "@/components/ErrorAlert";
import { useCan } from "@/components/MeProvider";
import { ReasonModal } from "@/components/ReasonModal";
import { useCancelDocument } from "@/hooks/use-cancel-document";
import { useDateFormat } from "@/hooks/use-date-format";
import { useDocumentAction } from "@/hooks/use-document";
import { useLocationLookup } from "@/hooks/use-lookup";
import { useResourceItem } from "@/hooks/use-resource";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import {
  countStep,
  isCounting,
  surplusNeedingValue,
  uncountedLines,
} from "@/lib/stock-counts";
import type { CountScanResult, StockCount, StockCountUnit } from "@/lib/types";

export default function StockCountPage() {
  const t = useTranslations("stockCounts");
  const tScan = useTranslations("stockCounts.scan");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const { formatDateTime } = useDateFormat();
  const { id } = useParams<{ id: string }>();
  const can = useCan();
  const queryClient = useQueryClient();

  const query = useResourceItem<StockCount>("stock-counts", id);
  const locations = useLocationLookup();

  const [closing, setClosing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmRefusal, setConfirmRefusal] = useState<string | null>(null);

  const close = useDocumentAction<StockCount>("stock-counts", id, { path: "/close" });
  const confirm = useDocumentAction<StockCount>("stock-counts", id, {
    path: "/confirm",
  });
  const cancelDoc = useCancelDocument("stock-counts", id, setActionError);
  const unscan = useDocumentAction<null, { imei: string }>("stock-counts", id, {
    method: "DELETE",
    path: (payload) => `/scan/${payload.imei}`,
  });

  const key = ["stock-counts", "item", id];

  /**
   * A scan names one row and the three totals, so the cache is patched at
   * that row rather than refetched — a count holds the whole shelf, and
   * re-reading hundreds of rows per beep is what §6 budgets against.
   */
  function applyScan(result: CountScanResult) {
    queryClient.setQueryData<StockCount>(key, (current) => {
      if (!current) return current;
      const totals = {
        matchedCount: result.matchedCount,
        missingCount: result.missingCount,
        unexpectedCount: result.unexpectedCount,
      };
      if (result.unit) {
        const unit = result.unit;
        const known = current.units.some((row) => row.id === unit.id);
        return {
          ...current,
          ...totals,
          units: known
            ? current.units.map((row) => (row.id === unit.id ? unit : row))
            : [...current.units, unit],
        };
      }
      if (result.line) {
        const line = result.line;
        return {
          ...current,
          ...totals,
          lines: current.lines.map((row) => (row.id === line.id ? line : row)),
        };
      }
      return { ...current, ...totals };
    });
  }

  /**
   * Unscanning is not symmetric, and the row's own `expected` flag says
   * which way it goes: a handset the snapshot knew about goes back to
   * missing, because the snapshot is history and deleting it would erase
   * what the shelf held when the count opened. One nobody expected simply
   * leaves.
   */
  function applyUnscan(unit: StockCountUnit) {
    queryClient.setQueryData<StockCount>(key, (current) => {
      if (!current) return current;
      if (unit.expected) {
        return {
          ...current,
          matchedCount: current.matchedCount - 1,
          missingCount: current.missingCount + 1,
          units: current.units.map((row) =>
            row.id === unit.id
              ? { ...row, scanned: false, outcome: "missing" as const }
              : row,
          ),
        };
      }
      return {
        ...current,
        unexpectedCount: current.unexpectedCount - 1,
        units: current.units.filter((row) => row.id !== unit.id),
      };
    });
  }

  if (query.isLoading) return <DetailLoading />;

  const count = query.data;
  if (query.isError || !count) {
    return (
      <DetailError
        message={query.error instanceof Error ? query.error.message : t("notFound")}
      />
    );
  }

  const step = countStep(count);
  const counting = isCounting(count);
  const canRun = can(Permission.StockCount.Run);
  const canConfirm = can(Permission.StockCount.Confirm);
  const surplus = surplusNeedingValue(count);
  const uncounted = uncountedLines(count);
  // Without Cost.View the worklist cannot be computed honestly, so the button
  // is left enabled and the server's refusal is what stops a bad confirm.
  const blockedBySurplus = can(Permission.Cost.View) && surplus.length > 0;

  async function runClose() {
    setActionError(null);
    try {
      await close.mutateAsync(undefined as never);
      notifySuccess(t("closed"));
      setClosing(false);
    } catch (error) {
      setClosing(false);
      setActionError(errorMessage(error, tCommon("retry")));
    }
  }

  async function runConfirm() {
    setActionError(null);
    setConfirmRefusal(null);
    try {
      await confirm.mutateAsync(undefined as never);
      notifySuccess(tDoc("confirmed"));
      setConfirming(false);
    } catch (error) {
      // FR-6.4b names every offending IMEI in one message, so the refusal is
      // a worklist and belongs on the page, not in a toast that vanishes.
      setConfirming(false);
      setConfirmRefusal(errorMessage(error, tCommon("retry")));
    }
  }

  async function removeUnit(unit: StockCountUnit) {
    setActionError(null);
    try {
      await unscan.mutateAsync({ imei: unit.imei });
      applyUnscan(unit);
      notifySuccess(tScan("unscanned", { imei: unit.imei }));
    } catch (error) {
      setActionError(errorMessage(error, tCommon("retry")));
    }
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <Stack gap="2xs">
          <Group gap="sm">
            <Title order={2}>{count.number}</Title>
            <CountStepBadge count={count} />
          </Group>
          <Text size="sm" c="dimmed">
            {t("location")}: {locations.get(count.locationId) ?? tCommon("none")}
            {" · "}
            {tDoc("created")}: {formatDateTime(count.createdAt)}
            {count.closedAt && (
              <>
                {" · "}
                {t("closedAt")}: {formatDateTime(count.closedAt)}
              </>
            )}
          </Text>
          {count.note && <Text size="sm">{count.note}</Text>}
        </Stack>

        <Group gap="sm">
          {counting && canRun && (
            <Button onClick={() => setClosing(true)}>{t("closeAction")}</Button>
          )}
          {step === "closed" && canConfirm && (
            <Button
              disabled={blockedBySurplus}
              onClick={() => setConfirming(true)}
            >
              {tDoc("confirmAction")}
            </Button>
          )}
          {step !== "cancelled" && can(Permission.Document.Cancel) && (
            <Button color="red" variant="light" onClick={cancelDoc.open}>
              {tDoc("cancelAction")}
            </Button>
          )}
        </Group>
      </Group>

      {step === "cancelled" && (
        <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
          {t("cancelledNotice")}
        </Alert>
      )}

      {step === "closed" && (
        <Alert variant="light" color="yellow" icon={<IconAlertCircle size={18} />}>
          {t("closedNotice")}
        </Alert>
      )}

      <ErrorAlert message={actionError} />
      <ErrorAlert message={confirmRefusal} />

      {counting && canRun && (
        <CountScanConsole count={count} onScanned={applyScan} />
      )}

      {step === "closed" && (
        <SurplusWorklist count={count} units={surplus} onFixed={applyScan} />
      )}

      <Card withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Text fw={500}>{t("handsets")}</Text>
          <DiscrepancyReport
            count={count}
            onUnscan={counting && canRun ? removeUnit : undefined}
            unscanning={unscan.isPending}
          />
        </Stack>
      </Card>

      <Card withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Group justify="space-between" align="flex-end" wrap="wrap">
            <Text fw={500}>{t("accessories")}</Text>
            {counting && uncounted.length > 0 && (
              <Text size="sm" c="orange">
                {t("uncountedWarning", { count: uncounted.length })}
              </Text>
            )}
          </Group>
          <CountLineTable
            count={count}
            editable={counting && canRun}
            onCounted={(updated) => queryClient.setQueryData<StockCount>(key, updated)}
            onError={setActionError}
          />
        </Stack>
      </Card>

      <ReasonModal
        opened={closing}
        onClose={() => setClosing(false)}
        title={t("closeTitle")}
        description={t("closeBody")}
        submitLabel={t("closeAction")}
        busy={close.isPending}
        error={actionError}
        onSubmit={runClose}
      />

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
