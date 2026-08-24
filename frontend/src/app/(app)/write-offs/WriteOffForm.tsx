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
  WRITE_OFF_REASONS,
  type Location,
  type WriteOff,
  type WriteOffReason,
} from "@/lib/types";

/**
 * FR-6.5: a Manager opens a write-off against a location with a mandatory
 * reason. It has no lines — every handset arrives by scan.
 *
 * The reason is closed rather than free text because §5.10 reports theft and
 * damage as different figures, and a typed sentence could not be counted.
 * A count shortage is deliberately not one of the options: "we looked and it
 * was gone" books `COUNT_ADJUSTMENT`, and stating it here would claim the
 * store knows what happened when it does not (§4.6).
 */
export function WriteOffForm() {
  const t = useTranslations("writeOffs");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const router = useRouter();

  const [locationId, setLocationId] = useState<string | null>(null);
  const [reason, setReason] = useState<WriteOffReason | null>(null);
  const [note, setNote] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);

  const locations = useResourceList<Location>("locations", {
    page: 1,
    pageSize: 200,
    isActive: true,
  });

  const create = useResourceCreate<WriteOff, Record<string, unknown>>("write-offs");

  const isValid = locationId !== null && reason !== null;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setShowErrors(true);
    setFormError(null);
    if (!isValid) return;

    try {
      const writeOff = await create.mutateAsync({
        locationId,
        reason,
        ...(note.trim() ? { note: note.trim() } : {}),
      });
      notifySuccess(tCommon("created"));
      router.push(`/write-offs/${writeOff!.id}`);
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
              onChange={(value) => setReason(value as WriteOffReason | null)}
              required
              error={showErrors && !reason ? tCommon("required") : null}
              data={WRITE_OFF_REASONS.map((value) => ({
                value,
                label: tDoc(`writeOffReason.${value}`),
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
