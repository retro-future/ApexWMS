"use client";

import { Alert, Button, PasswordInput, Stack } from "@mantine/core";
import { useForm } from "@mantine/form";
import { IconAlertCircle, IconInfoCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, apiSend } from "@/lib/api";

export function ChangePasswordForm({ forced }: { forced: boolean }) {
  const t = useTranslations("auth");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const form = useForm({
    initialValues: { currentPassword: "", newPassword: "", confirm: "" },
    validate: {
      currentPassword: (value) => (value ? null : tCommon("required")),
      newPassword: (value) =>
        value.length >= 8 ? null : t("passwordTooShort"),
      confirm: (value, values) =>
        value === values.newPassword ? null : t("passwordsDoNotMatch"),
    },
  });

  async function submit(values: typeof form.values) {
    setBusy(true);
    setError(null);
    try {
      await apiSend("POST", "/auth/change-password", {
        currentPassword: values.currentPassword,
        newPassword: values.newPassword,
      });

      // The backend revokes every refresh token on a password change, so the
      // session cannot survive this. Drop the cookies and start clean.
      await fetch("/api/auth/logout", { method: "POST" });
      router.replace("/login?changed=1");
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : tCommon("retry"));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={form.onSubmit(submit)} noValidate>
      <Stack gap="md">
        {forced && (
          <Alert variant="light" color="yellow" icon={<IconInfoCircle size={18} />}>
            {t("mustChangePassword")}
          </Alert>
        )}
        {error && (
          <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
            {error}
          </Alert>
        )}

        <PasswordInput
          label={t("currentPassword")}
          autoComplete="current-password"
          autoFocus
          {...form.getInputProps("currentPassword")}
        />
        <PasswordInput
          label={t("newPassword")}
          autoComplete="new-password"
          {...form.getInputProps("newPassword")}
        />
        <PasswordInput
          label={t("confirmNewPassword")}
          autoComplete="new-password"
          {...form.getInputProps("confirm")}
        />

        <Button type="submit" loading={busy} fullWidth mt="xs">
          {t("changePasswordAction")}
        </Button>
      </Stack>
    </form>
  );
}
