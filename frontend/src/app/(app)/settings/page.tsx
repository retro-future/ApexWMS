"use client";

import {
  Alert,
  Button,
  Card,
  FileInput,
  Group,
  Image,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { IconInfoCircle, IconUpload } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { DetailError, DetailLoading } from "@/components/DetailStates";
import { ErrorAlert } from "@/components/ErrorAlert";
import { useCan } from "@/components/MeProvider";
import { apiGet, apiSend } from "@/lib/api";
import { checkLogo, LOGO_TYPES, readLogoBase64 } from "@/lib/letterhead";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { TenantSettings } from "@/lib/types";

type Values = {
  timezone: string;
  businessName: string;
  address: string;
  // Carried through the form without a control of its own: the setting
  // gates nothing until the shift screens exist (W9 B5), and a PUT that
  // dropped it would silently turn it off.
  runsTill: boolean;
};

export default function SettingsPage() {
  const t = useTranslations("settings");
  const tCommon = useTranslations("common");
  const can = useCan();
  const manage = can(Permission.TenantSettings.Manage);
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const [logoError, setLogoError] = useState<string | null>(null);
  // Bumped on every logo write. The proxy forwards no Cache-Control, so
  // without this the browser may keep showing the logo that was replaced.
  const [logoVersion, setLogoVersion] = useState(0);

  const query = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiGet<TenantSettings>("/settings/tenant"),
  });

  const form = useForm<Values>({
    initialValues: { timezone: "", businessName: "", address: "", runsTill: false },
    validate: {
      timezone: (value) => (value.trim() ? null : tCommon("required")),
    },
  });

  const { setValues } = form;
  useEffect(() => {
    if (!query.data) return;
    setValues({
      timezone: query.data.timezone,
      businessName: query.data.businessName ?? "",
      address: query.data.address ?? "",
      runsTill: query.data.runsTill,
    });
  }, [query.data, setValues]);

  // PUT, not PATCH — the whole settings document is replaced, so every field
  // goes on every save. Sending the timezone alone blanks the letterhead.
  const mutation = useMutation({
    mutationFn: (values: Values) =>
      apiSend<TenantSettings>("PUT", "/settings/tenant", {
        timezone: values.timezone.trim(),
        businessName: values.businessName.trim() || null,
        address: values.address.trim() || null,
        runsTill: values.runsTill,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });

  // Its own endpoint and its own save: folding the image into the form's
  // submit would make one button do two unrelated writes.
  const logoMutation = useMutation({
    mutationFn: (content: string | null) =>
      apiSend<TenantSettings>(
        "PUT",
        "/settings/tenant/logo",
        content === null ? {} : { content },
      ),
    onSuccess: () => {
      setLogoVersion((version) => version + 1);
      return queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  async function submit(values: Values) {
    setFormError(null);
    try {
      await mutation.mutateAsync(values);
      notifySuccess(tCommon("saved"));
    } catch (err) {
      // 422 for anything that is not a real IANA zone name.
      setFormError(errorMessage(err, tCommon("retry")));
    }
  }

  async function pickLogo(file: File | null) {
    setLogoError(null);
    if (!file) return;

    const problem = checkLogo(file);
    if (problem) {
      setLogoError(problem === "tooLarge" ? t("logoTooLarge") : t("logoWrongType"));
      return;
    }

    try {
      await logoMutation.mutateAsync(await readLogoBase64(file));
      notifySuccess(tCommon("saved"));
    } catch (err) {
      setLogoError(errorMessage(err, tCommon("retry")));
    }
  }

  async function removeLogo() {
    setLogoError(null);
    try {
      await logoMutation.mutateAsync(null);
      notifySuccess(tCommon("saved"));
    } catch (err) {
      setLogoError(errorMessage(err, tCommon("retry")));
    }
  }

  if (query.isLoading) return <DetailLoading />;

  if (query.isError || !query.data) {
    return <DetailError message={errorMessage(query.error, tCommon("retry"))} />;
  }

  const hasLogo = query.data.hasLogo;

  return (
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

      <form onSubmit={form.onSubmit(submit)} noValidate>
        <Stack gap="lg">
          <ErrorAlert message={formError} />

          <Card withBorder radius="md" padding="lg">
            <Stack gap="md">
              <TextInput
                label={t("timezone")}
                description={t("timezoneHint")}
                placeholder="Asia/Tashkent"
                disabled={!manage}
                {...form.getInputProps("timezone")}
              />
              <TextInput
                label={t("businessName")}
                description={t("businessNameHint")}
                disabled={!manage}
                {...form.getInputProps("businessName")}
              />
              <Textarea
                label={t("address")}
                description={t("addressHint")}
                autosize
                minRows={2}
                maxRows={4}
                disabled={!manage}
                {...form.getInputProps("address")}
              />
            </Stack>
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

      <Card withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Stack gap="3xs">
            <Text fw={500}>{t("logo")}</Text>
            <Text size="sm" c="dimmed">
              {t("logoHint")}
            </Text>
          </Stack>

          <ErrorAlert message={logoError} />

          {hasLogo ? (
            <Image
              src={`/api/backend/settings/tenant/logo?v=${logoVersion}`}
              alt={t("logo")}
              h={72}
              w="auto"
              fit="contain"
            />
          ) : (
            <Text size="sm" c="dimmed">
              {t("logoNone")}
            </Text>
          )}

          {manage && (
            <Group gap="sm">
              <FileInput
                aria-label={t("logoChoose")}
                placeholder={t("logoChoose")}
                accept={LOGO_TYPES.join(",")}
                value={null}
                disabled={logoMutation.isPending}
                leftSection={<IconUpload size={16} />}
                onChange={pickLogo}
                w={{ base: "100%", sm: 280 }}
              />
              {hasLogo && (
                <Button
                  variant="light"
                  color="red"
                  loading={logoMutation.isPending}
                  onClick={removeLogo}
                >
                  {t("logoRemove")}
                </Button>
              )}
            </Group>
          )}
        </Stack>
      </Card>
    </Stack>
  );
}
