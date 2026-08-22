"use client";

import { Button, PasswordInput, Stack, TextInput } from "@mantine/core";
import { useForm } from "@mantine/form";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { messageFromDetail } from "@/lib/api";

export function AcceptInviteForm({ token }: { token: string }) {
  const t = useTranslations("auth");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const form = useForm({
    initialValues: { fullName: "", password: "", confirm: "" },
    validate: {
      password: (value) => (value.length >= 8 ? null : t("passwordTooShort")),
      confirm: (value, values) =>
        value === values.password ? null : t("passwordsDoNotMatch"),
    },
  });

  async function submit(values: typeof form.values) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/accept-invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          password: values.password,
          fullName: values.fullName.trim() || null,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setError(messageFromDetail(body?.detail, tCommon("retry")));
        return;
      }

      router.replace("/login");
    } catch {
      setError(tCommon("retry"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={form.onSubmit(submit)} noValidate>
      <Stack gap="md">
        <ErrorAlert message={error} />

        <TextInput
          label={`${t("fullName")} (${tCommon("optional")})`}
          autoComplete="name"
          autoFocus
          {...form.getInputProps("fullName")}
        />
        <PasswordInput
          label={t("password")}
          autoComplete="new-password"
          {...form.getInputProps("password")}
        />
        <PasswordInput
          label={t("confirmNewPassword")}
          autoComplete="new-password"
          {...form.getInputProps("confirm")}
        />

        <Button type="submit" loading={busy} fullWidth mt="xs">
          {t("acceptInviteAction")}
        </Button>
      </Stack>
    </form>
  );
}
