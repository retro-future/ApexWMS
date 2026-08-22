"use client";

import { Alert, Button, PasswordInput, Stack, TextInput } from "@mantine/core";
import { useForm } from "@mantine/form";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { messageFromDetail } from "@/lib/api";

export function LoginForm({ notice }: { notice?: string }) {
  const t = useTranslations("auth");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const form = useForm({
    initialValues: { email: "", password: "" },
    validate: {
      email: (value) => (value.trim() ? null : tCommon("required")),
      password: (value) => (value ? null : tCommon("required")),
    },
  });

  async function submit(values: { email: string; password: string }) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: values.email.trim(),
          password: values.password,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setError(messageFromDetail(body?.detail, tCommon("retry")));
        return;
      }

      // The app layout decides where to land (dashboard, forced password
      // change, or the platform-operator notice) — it already knows.
      router.replace("/");
      router.refresh();
    } catch {
      setError(tCommon("retry"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={form.onSubmit(submit)} noValidate>
      <Stack gap="md">
        {notice && (
          <Alert variant="light" color="yellow" icon={<IconAlertCircle size={18} />}>
            {notice}
          </Alert>
        )}
        <ErrorAlert message={error} />

        <TextInput
          label={t("email")}
          type="email"
          autoComplete="username"
          autoFocus
          {...form.getInputProps("email")}
        />
        <PasswordInput
          label={t("password")}
          autoComplete="current-password"
          {...form.getInputProps("password")}
        />

        <Button type="submit" loading={busy} fullWidth mt="xs">
          {t("signInAction")}
        </Button>
      </Stack>
    </form>
  );
}
