"use client";

import { useFormatter } from "next-intl";

/**
 * Locale-aware date formatting, backed by next-intl's `useFormatter` so a
 * timestamp renders in the operator's chosen locale (uz/ru/en) rather than
 * whatever locale the browser happens to be set to.
 */
export function useDateFormat() {
  const format = useFormatter();

  return {
    /** e.g. "Aug 22, 2026" */
    formatDate: (iso: string) => format.dateTime(new Date(iso), { dateStyle: "medium" }),
    /** e.g. "Aug 22, 2026, 3:45 PM" */
    formatDateTime: (iso: string) =>
      format.dateTime(new Date(iso), { dateStyle: "medium", timeStyle: "short" }),
  };
}
