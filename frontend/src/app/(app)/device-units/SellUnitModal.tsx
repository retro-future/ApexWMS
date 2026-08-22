"use client";

import { Alert, Select, Text } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { useResourceList } from "@/hooks/use-resource";
import { apiSend } from "@/lib/api";
import { errorMessage } from "@/lib/notify";
import type { Customer, DeviceUnit, Location, SalesInvoice } from "@/lib/types";

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
export function SellUnitModal({
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
