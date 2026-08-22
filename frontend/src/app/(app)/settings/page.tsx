"use client";

import { Alert, Button, Card, Group, Stack, Text, TextInput, Title } from "@mantine/core";
import { useForm } from "@mantine/form";
import { IconAlertCircle, IconInfoCircle } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { DetailError, DetailLoading } from "@/components/DetailStates";
import { useCan } from "@/components/MeProvider";
import { apiGet, apiSend } from "@/lib/api";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { TenantSettings } from "@/lib/types";

export default function SettingsPage() {
  const t = useTranslations("settings");
  const tCommon = useTranslations("common");
  const can = useCan();
  const manage = can(Permission.TenantSettings.Manage);
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiGet<TenantSettings>("/settings/tenant"),
  });

  const form = useForm<{ timezone: string }>({
    initialValues: { timezone: "" },
    validate: {
      timezone: (value) => (value.trim() ? null : tCommon("required")),
    },
  });

  const { setValues } = form;
  useEffect(() => {
    if (query.data) setValues({ timezone: query.data.timezone });
  }, [query.data, setValues]);

  // PUT, not PATCH — the whole settings document is replaced.
  const mutation = useMutation({
    mutationFn: (timezone: string) =>
      apiSend<TenantSettings>("PUT", "/settings/tenant", { timezone }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });

  async function submit(values: { timezone: string }) {
    setFormError(null);
    try {
      await mutation.mutateAsync(values.timezone.trim());
      notifySuccess(tCommon("saved"));
    } catch (err) {
      // 422 for anything that is not a real IANA zone name.
      setFormError(errorMessage(err, tCommon("retry")));
    }
  }

  if (query.isLoading) return <DetailLoading />;

  if (query.isError) {
    return <DetailError message={errorMessage(query.error, tCommon("retry"))} />;
  }

  return (
    <form onSubmit={form.onSubmit(submit)} noValidate>
      <Stack gap="lg" maw={560}>
        <Stack gap="3xs">
          <Title order={2}>{t("title")}</Title>
          <Text size="sm" c="dimmed">
            {t("subtitle")}
          </Text>
        </Stack>

        {!manage && (
          <Alert variant="light" color="blue" icon={<IconInfoCircle size={18} />}>
            {t("readOnly")}
          </Alert>
        )}

        {formError && (
          <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
            {formError}
          </Alert>
        )}

        <Card withBorder radius="md" padding="lg">
          <TextInput
            label={t("timezone")}
            description={t("timezoneHint")}
            placeholder="Asia/Tashkent"
            disabled={!manage}
            {...form.getInputProps("timezone")}
          />
        </Card>

        {manage && (
          <Group justify="flex-end">
            <Button type="submit" loading={mutation.isPending}>
              {tCommon("save")}
            </Button>
          </Group>
        )}
      </Stack>
    </form>
  );
}
