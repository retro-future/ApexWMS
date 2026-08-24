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

import { ErrorAlert } from "@/components/ErrorAlert";
import { useResourceCreate, useResourceList } from "@/hooks/use-resource";
import { ApiError } from "@/lib/api";
import { errorMessage, notifySuccess } from "@/lib/notify";
import type { Location, StockCount } from "@/lib/types";

/**
 * FR-6.1: opening a count snapshots the shelf at that instant — one row per
 * handset on hand, one line per accessory level including the empty ones.
 *
 * The snapshot is taken now rather than computed at close, because a count
 * takes hours while sales keep happening, and recomputing at close would
 * report a phone sold mid-count as missing. The flip side is the warning
 * below: a location that is actively receiving while being counted produces
 * a report nobody can trust, and no code can fix that afterwards.
 */
export function StockCountForm() {
  const t = useTranslations("stockCounts");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const router = useRouter();

  const [locationId, setLocationId] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);

  const locations = useResourceList<Location>("locations", {
    page: 1,
    pageSize: 200,
    isActive: true,
  });

  const create = useResourceCreate<StockCount, Record<string, unknown>>(
    "stock-counts",
  );

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setShowErrors(true);
    setFormError(null);
    if (!locationId) return;

    try {
      const count = await create.mutateAsync({
        locationId,
        ...(note.trim() ? { note: note.trim() } : {}),
      });
      notifySuccess(tCommon("created"));
      router.push(`/stock-counts/${count!.id}`);
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

        <Alert variant="light" icon={<IconAlertCircle size={18} />}>
          {t("snapshotWarning")}
        </Alert>

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
            {t("open")}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
