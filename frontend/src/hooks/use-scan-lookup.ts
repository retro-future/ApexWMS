"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";

import { apiGet, queryString } from "@/lib/api";
import { notifyError } from "@/lib/notify";
import type { ScanLookup } from "@/lib/types";

/**
 * Look a scanned code up and jump straight to what it named (FR-7.1, FR-7.2).
 *
 * Shared by every scan surface (the header bar, the dashboard's mobile
 * card) so a barcode and an IMEI resolve to the same place everywhere.
 */
export function useScanLookup() {
  const t = useTranslations("scan");
  const router = useRouter();

  return useMutation({
    mutationFn: (code: string) =>
      apiGet<ScanLookup>(`/scan/lookup${queryString({ code })}`),
    onSuccess: (result) => {
      if (result.kind === "device" && result.device) {
        router.push(`/device-units/${result.device.id}`);
      } else if (result.product) {
        router.push(`/products/${result.product.id}`);
      }
    },
    // A 404 is the ordinary answer to an unknown code, not a failure worth
    // an alert box. The operator scans the next thing.
    onError: (_error, code) => notifyError(t("notFound", { code })),
  });
}
