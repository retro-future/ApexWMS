"use client";

import { Anchor, Badge, Center, Group, Loader, Stack, Text, Timeline } from "@mantine/core";
import {
  IconAdjustments,
  IconArrowBackUp,
  IconPackageImport,
  IconReceipt,
  IconReceiptRefund,
  IconTag,
  IconTrashX,
} from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { DocumentLink } from "@/app/(app)/reports/DocumentLink";
import { ErrorAlert } from "@/components/ErrorAlert";
import { useDateFormat } from "@/hooks/use-date-format";
import { apiGet } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { DeviceTrace, TraceEvent, TraceEventKind } from "@/lib/types";

const ICONS: Record<TraceEventKind, React.ElementType> = {
  received: IconPackageImport,
  priced: IconTag,
  sold: IconReceipt,
  returned_by_customer: IconReceiptRefund,
  returned_to_supplier: IconArrowBackUp,
  written_off: IconTrashX,
  count_adjustment: IconAdjustments,
};

/**
 * FR-9.2: one handset's whole life, in order.
 *
 * Bought, priced, cut twice, sold below asking, with the name of whoever
 * approved that. The three sources behind it are append-only, so this is a
 * read of what happened and never a reconstruction — there is no
 * condition-change line here because changing a condition writes no log,
 * and a timeline that guesses a date is worse than one missing a line.
 */
export function DeviceTraceTimeline({ deviceUnitId }: { deviceUnitId: string }) {
  const t = useTranslations("reports");
  const tCommon = useTranslations("common");

  const query = useQuery<DeviceTrace>({
    queryKey: ["device-units", "item", deviceUnitId, "trace"],
    queryFn: () => apiGet<DeviceTrace>(`/device-units/${deviceUnitId}/trace`),
  });

  if (query.isLoading) {
    return (
      <Center p="md">
        <Loader size="sm" />
      </Center>
    );
  }
  if (query.error || !query.data) {
    return (
      <ErrorAlert
        message={
          query.error instanceof Error ? query.error.message : tCommon("retry")
        }
      />
    );
  }

  const { events } = query.data;

  if (events.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        {t("noTraceEvents")}
      </Text>
    );
  }

  return (
    <Timeline active={events.length} bulletSize={24} lineWidth={2}>
      {events.map((event, index) => {
        const Icon = ICONS[event.kind];
        return (
          <Timeline.Item
            key={`${event.kind}-${event.occurredAt}-${index}`}
            bullet={<Icon size={14} stroke={1.5} />}
            title={t(`traceKind.${event.kind}`)}
          >
            <TraceEventBody event={event} />
          </Timeline.Item>
        );
      })}
    </Timeline>
  );
}

function TraceEventBody({
  event,
}: {
  event: TraceEvent;
}) {
  const t = useTranslations("reports");
  const tUnits = useTranslations("deviceUnits");
  const tCommon = useTranslations("common");
  const { formatDateTime } = useDateFormat();

  return (
    <Stack gap="3xs" mt="3xs">
      <Group gap="xs" wrap="wrap">
        <Text size="xs" c="dimmed">
          {formatDateTime(event.occurredAt)}
        </Text>
        <Text size="xs" c="dimmed">
          {event.userName ?? t("unattributed")}
        </Text>
        {event.locationName && (
          <Text size="xs" c="dimmed">
            {event.locationName}
          </Text>
        )}
        {event.documentType && event.documentId && (
          <DocumentLink
            documentType={event.documentType}
            documentId={event.documentId}
            documentNumber={event.documentNumber}
          />
        )}
      </Group>

      {event.origin && (
        <Text size="sm">
          {event.origin.acquisitionSource === "trade_in"
            ? t("tradedInFrom", {
                name: event.origin.customerName ?? tCommon("none"),
              })
            : t("receivedFrom", {
                name: event.origin.supplierName ?? tCommon("none"),
              })}
        </Text>
      )}

      {event.kind === "priced" && event.newPrice !== null && (
        <Text size="sm">
          {event.oldPrice === null
            ? tUnits("priceFirst", {
                price: formatMoney(event.newPrice),
              })
            : tUnits("priceChanged", {
                oldPrice: formatMoney(event.oldPrice),
                newPrice: formatMoney(event.newPrice),
              })}
        </Text>
      )}

      {event.sale && (
        <Stack gap="3xs">
          <Group gap="xs" wrap="wrap">
            <Anchor
              component={Link}
              href={`/invoices/${event.sale.invoiceId}`}
              size="sm"
              fw={500}
            >
              {event.sale.invoiceNumber}
            </Anchor>
            <Text size="sm">
              {event.sale.customerName ?? t("walkIn")}
            </Text>
            {event.sale.chargedPrice !== null && (
              <Text size="sm" fw={600}>
                {formatMoney(event.sale.chargedPrice)}
              </Text>
            )}
          </Group>
          {/* The point of the line: what the system resolved, what was
              charged instead, and who signed off (FR-4.5f). */}
          {event.sale.priceApprovedBy && (
            <Group gap="xs" wrap="wrap">
              <Badge size="xs" variant="light" color="orange">
                {t("overridden")}
              </Badge>
              {event.sale.resolvedPrice !== null && (
                <Text size="xs" c="dimmed">
                  {t("resolvedWas", {
                    price: formatMoney(event.sale.resolvedPrice),
                  })}
                </Text>
              )}
              <Text size="xs" c="dimmed">
                {event.sale.priceApprovedByName ?? t("unattributed")}
              </Text>
            </Group>
          )}
          {event.sale.priceNote && (
            <Text size="xs" c="dimmed">
              {event.sale.priceNote}
            </Text>
          )}
        </Stack>
      )}

      {event.note && (
        <Text size="xs" c="dimmed">
          {event.note}
        </Text>
      )}
    </Stack>
  );
}
