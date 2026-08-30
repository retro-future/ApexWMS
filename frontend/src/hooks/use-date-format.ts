"use client";

/**
 * Dates render in a fixed ISO-style format (2026-08-30), the same in every
 * locale. next-intl's locale-aware `dateStyle` produced "2026 M08 30" under uz,
 * which operators read as broken.
 */
const dateFmt = new Intl.DateTimeFormat("en-CA", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const timeFmt = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function useDateFormat() {
  return {
    /** e.g. "2026-08-30" */
    formatDate: (iso: string) => dateFmt.format(new Date(iso)),
    /** e.g. "2026-08-30 15:45" */
    formatDateTime: (iso: string) => {
      const d = new Date(iso);
      return `${dateFmt.format(d)} ${timeFmt.format(d)}`;
    },
  };
}
