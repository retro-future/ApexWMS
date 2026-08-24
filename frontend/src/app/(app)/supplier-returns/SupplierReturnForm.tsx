"use client";

import { Button, Card, Group, Select, Stack, Textarea, Title } from "@mantine/core";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { useResourceCreate, useResourceList } from "@/hooks/use-resource";
import { ApiError } from "@/lib/api";
import { errorMessage, notifySuccess } from "@/lib/notify";
import {
  SUPPLIER_RETURN_REASONS,
  type Location,
  type Supplier,
  type SupplierReturn,
  type SupplierReturnReason,
} from "@/lib/types";

/**
 * FR-5.1: a Manager opens a return against a supplier, a location and a
 * stated reason. It has no lines — every handset arrives by scan, and only
 * one currently `IN_STOCK` at this location may be added (FR-5.2).
 *
 * The reason is mandatory and closed: "what did this supplier send us
 * defective" is the question the list filter exists to answer, and free text
 * could not answer it.
 */
export function SupplierReturnForm() {
  const t = useTranslations("supplierReturns");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const router = useRouter();

  const [supplierId, setSupplierId] = useState<string | null>(null);
  const [locationId, setLocationId] = useState<string | null>(null);
  const [reason, setReason] = useState<SupplierReturnReason | null>(null);
  const [note, setNote] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);

  const reference = { page: 1, pageSize: 200, isActive: true };
  const suppliers = useResourceList<Supplier>("suppliers", reference);
  const locations = useResourceList<Location>("locations", reference);

  const create = useResourceCreate<SupplierReturn, Record<string, unknown>>(
    "supplier-returns",
  );

  const isValid = supplierId !== null && locationId !== null && reason !== null;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setShowErrors(true);
    setFormError(null);
    if (!isValid) return;

    try {
      const supplierReturn = await create.mutateAsync({
        supplierId,
        locationId,
        reason,
        ...(note.trim() ? { note: note.trim() } : {}),
      });
      notifySuccess(tCommon("created"));
      router.push(`/supplier-returns/${supplierReturn!.id}`);
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
              label={t("supplier")}
              placeholder={t("supplier")}
              value={supplierId}
              onChange={setSupplierId}
              searchable
              required
              error={showErrors && !supplierId ? tCommon("required") : null}
              data={(suppliers.data?.items ?? []).map((supplier) => ({
                value: supplier.id,
                label: supplier.name,
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
              onChange={(value) => setReason(value as SupplierReturnReason | null)}
              required
              error={showErrors && !reason ? tCommon("required") : null}
              data={SUPPLIER_RETURN_REASONS.map((value) => ({
                value,
                label: tDoc(`returnReason.${value}`),
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
