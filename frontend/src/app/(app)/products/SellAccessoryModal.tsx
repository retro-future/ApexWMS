"use client";

import { Alert, NumberInput, Select, Text } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { useResourceList } from "@/hooks/use-resource";
import { apiSend } from "@/lib/api";
import { errorMessage } from "@/lib/notify";
import type { Customer, Location, Product, SalesInvoice } from "@/lib/types";

/**
 * The counter's shortcut for an accessory: open an invoice and put this
 * product on it (FR-4.1, FR-4.2c), without going to the invoice list.
 *
 * The two calls are not atomic on purpose: if the line is refused (no
 * catalog price, or nothing in stock), the draft invoice still exists and
 * the operator lands on it.
 */
export function SellAccessoryModal({
  product,
  onClose,
}: {
  product: Product;
  onClose: () => void;
}) {
  const tSell = useTranslations("invoices.sell");
  const tInvoices = useTranslations("invoices");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const router = useRouter();

  const [locationId, setLocationId] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [quantity, setQuantity] = useState<number>(1);
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
      await apiSend("POST", `/invoices/${invoice!.id}/lines`, {
        productId: product.id,
        quantity,
      });
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
      title={tSell("sellAccessoryTitle")}
      onSubmit={submit}
      busy={start.isPending}
      error={error}
      submitLabel={tSell("sellAccessory")}
    >
      <Text size="sm" c="dimmed">
        {tSell("sellAccessoryBody")}
      </Text>

      {product.defaultSalePriceMinor === null && (
        <Alert variant="light" color="yellow" icon={<IconAlertCircle size={18} />}>
          {tSell("sellAccessoryUnpriced")}
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
      <NumberInput
        label={tDoc("quantity")}
        value={quantity}
        onChange={(value) => setQuantity(typeof value === "number" ? value : 1)}
        min={1}
        max={999}
        allowDecimal={false}
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
