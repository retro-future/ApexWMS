"use client";

import {
  Alert,
  Button,
  Card,
  Group,
  Select,
  Stack,
  Textarea,
  Title,
} from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useResourceCreate, useResourceList } from "@/hooks/use-resource";
import { ApiError } from "@/lib/api";
import { errorMessage, notifySuccess } from "@/lib/notify";
import type { Customer, Location, SalesInvoice } from "@/lib/types";

/**
 * FR-4.1: a Seller opens an invoice with a location and, optionally, a
 * customer. It has no lines — every line arrives by scan (FR-4.2), and
 * there is no endpoint that adds one any other way.
 *
 * The three fields here are also the only chance to set them: there is no
 * `PATCH /invoices/{id}`, so an invoice raised against the wrong location
 * is abandoned and re-opened rather than corrected.
 */
export function InvoiceForm() {
  const t = useTranslations("invoices");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const router = useRouter();

  const [locationId, setLocationId] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);

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
  const create = useResourceCreate<SalesInvoice, Record<string, unknown>>("invoices");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setShowErrors(true);
    setFormError(null);
    if (!locationId) return;

    try {
      const invoice = await create.mutateAsync({
        locationId,
        // Omitted rather than null: no customer is a walk-in, which is a
        // normal sale and not a missing field.
        ...(customerId ? { customerId } : {}),
        ...(note.trim() ? { note: note.trim() } : {}),
      });
      notifySuccess(tCommon("created"));
      router.push(`/invoices/${invoice!.id}`);
    } catch (error) {
      if (error instanceof ApiError) setFormError(error.message);
      else setFormError(errorMessage(error, tCommon("retry")));
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="lg" maw={640}>
        <Title order={2}>{t("newTitle")}</Title>

        {formError && (
          <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
            {formError}
          </Alert>
        )}

        <Card withBorder radius="md" padding="lg">
          <Stack gap="md">
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
              label={t("customer")}
              description={t("customerHint")}
              placeholder={t("walkIn")}
              value={customerId}
              onChange={setCustomerId}
              searchable
              clearable
              data={(customers.data?.items ?? []).map((customer) => ({
                value: customer.id,
                label: customer.fullName,
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
