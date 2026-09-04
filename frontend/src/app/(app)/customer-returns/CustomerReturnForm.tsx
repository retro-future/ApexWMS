"use client";

import { Button, Card, Group, Select, Stack, Textarea, Title } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { useResourceCreate, useResourceList } from "@/hooks/use-resource";
import { ApiError } from "@/lib/api";
import { errorMessage, notifySuccess } from "@/lib/notify";
import {
  CUSTOMER_RETURN_REASONS,
  type CustomerReturn,
  type CustomerReturnReason,
  type Location,
  type SalesInvoice,
} from "@/lib/types";

/**
 * FR-4.9: a Manager opens a return against a confirmed sale, a location and
 * a stated reason. It has no lines — every item arrives by scan, and only
 * something this invoice actually sold may be added (FR-4.9a).
 *
 * The invoice picker is searchable and confirmed-only, because a draft sold
 * nothing and a cancelled sale already gave everything back.
 *
 * The location is the return's own rather than the invoice's: goods sold
 * from a shop that has since closed still have to land somewhere.
 */
export function CustomerReturnForm() {
  const t = useTranslations("customerReturns");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const router = useRouter();

  // Arriving from an invoice's "return goods" button preselects the sale.
  const fromInvoice = useSearchParams().get("invoice");

  const [salesInvoiceId, setSalesInvoiceId] = useState<string | null>(fromInvoice);
  const [locationId, setLocationId] = useState<string | null>(null);
  const [reason, setReason] = useState<CustomerReturnReason | null>(null);
  const [note, setNote] = useState("");
  const [invoiceSearch, setInvoiceSearch] = useState("");
  const [debouncedInvoiceSearch] = useDebouncedValue(invoiceSearch, 300);
  const [formError, setFormError] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);

  const locations = useResourceList<Location>("locations", {
    page: 1,
    pageSize: 200,
    isActive: true,
  });
  const invoices = useResourceList<SalesInvoice>("invoices", {
    page: 1,
    pageSize: 50,
    status: "confirmed",
    search: debouncedInvoiceSearch || undefined,
  });

  const create = useResourceCreate<CustomerReturn, Record<string, unknown>>(
    "customer-returns",
  );

  const isValid =
    salesInvoiceId !== null && locationId !== null && reason !== null;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setShowErrors(true);
    setFormError(null);
    if (!isValid) return;

    try {
      const document = await create.mutateAsync({
        salesInvoiceId,
        locationId,
        reason,
        ...(note.trim() ? { note: note.trim() } : {}),
      });
      notifySuccess(tCommon("created"));
      router.push(`/customer-returns/${document!.id}`);
    } catch (error) {
      if (error instanceof ApiError) setFormError(error.message);
      else setFormError(errorMessage(error, tCommon("retry")));
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="lg" maw={640}>
        <Title order={2}>{t("newTitle")}</Title>

        <ErrorAlert message={formError} />

        <Card withBorder radius="md" padding="lg">
          <Stack gap="md">
            <Select
              label={t("invoice")}
              description={t("invoiceHint")}
              placeholder={t("invoice")}
              value={salesInvoiceId}
              onChange={setSalesInvoiceId}
              searchable
              searchValue={invoiceSearch}
              onSearchChange={setInvoiceSearch}
              required
              error={showErrors && !salesInvoiceId ? tCommon("required") : null}
              data={(invoices.data?.items ?? []).map((invoice) => ({
                value: invoice.id,
                label: invoice.number,
              }))}
            />

            <Select
              label={t("location")}
              description={t("locationHint")}
              placeholder={t("location")}
              value={locationId}
              onChange={setLocationId}
              searchable
              required
              error={showErrors && !locationId ? tCommon("required") : null}
              data={(locations.data?.items ?? []).map((location) => ({
                value: location.id,
                label: location.name,
              }))}
            />

            <Select
              label={tDoc("reason")}
              description={t("reasonHint")}
              placeholder={tDoc("reason")}
              value={reason}
              onChange={(value) => setReason(value as CustomerReturnReason | null)}
              required
              error={showErrors && !reason ? tCommon("required") : null}
              data={CUSTOMER_RETURN_REASONS.map((value) => ({
                value,
                label: t(`reason.${value}`),
              }))}
            />

            <Textarea
              label={tDoc("note")}
              description={tCommon("optional")}
              value={note}
              onChange={(event) => setNote(event.currentTarget.value)}
              autosize
              minRows={2}
            />
          </Stack>
        </Card>

        <Group justify="flex-end">
          <Button variant="default" onClick={() => router.back()}>
            {tCommon("cancel")}
          </Button>
          <Button type="submit" loading={create.isPending}>
            {tCommon("create")}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
