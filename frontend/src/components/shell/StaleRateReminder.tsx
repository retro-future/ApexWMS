"use client";

import { notifications } from "@mantine/notifications";
import { useTranslations } from "next-intl";
import { useEffect } from "react";

import { useCan } from "@/components/MeProvider";
import { useCurrentRates } from "@/hooks/use-exchange-rates";
import { Permission } from "@/lib/permissions";

const SHOWN_KEY = "apexwms.staleRateNoticeShown";

/**
 * Nags whoever can fix it, once per session, when the rate on file is
 * yesterday's or older.
 *
 * A session flag rather than a render guard: this sits in the shell, so
 * without one the notice would reappear on every navigation.
 */
export function StaleRateReminder() {
  const t = useTranslations("rates");
  const can = useCan();
  const { data } = useCurrentRates();
  const mayManage = can(Permission.ExchangeRate.Manage);
  const stale = Boolean(data?.sale?.isStale || data?.buyback?.isStale);

  useEffect(() => {
    if (!stale || !mayManage) return;
    if (sessionStorage.getItem(SHOWN_KEY)) return;
    sessionStorage.setItem(SHOWN_KEY, "1");
    notifications.show({
      title: t("staleTitle"),
      message: t("staleBody"),
      color: "yellow",
      autoClose: false,
    });
  }, [stale, mayManage, t]);

  return null;
}
