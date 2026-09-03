"use client";

import { ActionIcon, Menu } from "@mantine/core";
import { IconLanguage } from "@tabler/icons-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { LOCALES, LOCALE_LABELS, type Locale } from "@/i18n/config";
import { CSRF_HEADERS } from "@/lib/csrf";

export function LanguageSwitcher() {
  const t = useTranslations("nav");
  const active = useLocale();
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function choose(locale: Locale) {
    if (locale === active) return;
    startTransition(async () => {
      await fetch("/api/auth/locale", {
        method: "POST",
        headers: { ...CSRF_HEADERS, "Content-Type": "application/json" },
        body: JSON.stringify({ locale }),
      });
      // Messages are resolved on the server, so the tree has to re-render.
      router.refresh();
    });
  }

  return (
    <Menu shadow="md" width={180} position="bottom-end">
      <Menu.Target>
        <ActionIcon
          variant="subtle"
          size="lg"
          aria-label={t("language")}
          loading={pending}
        >
          <IconLanguage size={20} stroke={1.5} />
        </ActionIcon>
      </Menu.Target>
      <Menu.Dropdown>
        {LOCALES.map((locale) => (
          <Menu.Item
            key={locale}
            onClick={() => choose(locale)}
            fw={locale === active ? 600 : 400}
          >
            {LOCALE_LABELS[locale]}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
