"use client";

import { Loader, TextInput } from "@mantine/core";
import { IconBarcode } from "@tabler/icons-react";
import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useCan } from "@/components/MeProvider";
import { apiGet, queryString } from "@/lib/api";
import { notifyError } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { ScanLookup } from "@/lib/types";

/**
 * The "customer walks in with a phone" bar (FR-7.1, FR-7.2).
 *
 * The scanner does not know whether it read an IMEI off a handset or a
 * barcode off a box, so neither does this: one call goes out and the
 * server states which kind it found. It is also the only way into a
 * handset's page — a device unit is reached by its IMEI, never by a UUID
 * anyone could type.
 */
export function ScanBar() {
  const t = useTranslations("scan");
  const router = useRouter();
  const can = useCan();
  const [code, setCode] = useState("");

  const lookup = useMutation({
    mutationFn: (scanned: string) =>
      apiGet<ScanLookup>(`/scan/lookup${queryString({ code: scanned })}`),
    onSuccess: (result) => {
      setCode("");
      if (result.kind === "device" && result.device) {
        router.push(`/device-units/${result.device.id}`);
      } else if (result.product) {
        router.push(`/products/${result.product.id}`);
      }
    },
    // A 404 is the ordinary answer to an unknown code, not a failure worth
    // an alert box — the operator scans the next thing.
    onError: () => notifyError(t("notFound", { code })),
  });

  if (!can(Permission.Scan.Lookup)) return null;

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        const scanned = code.trim();
        if (scanned) lookup.mutate(scanned);
      }}
    >
      <TextInput
        value={code}
        onChange={(event) => setCode(event.currentTarget.value)}
        placeholder={t("placeholder")}
        aria-label={t("placeholder")}
        leftSection={<IconBarcode size={18} stroke={1.5} />}
        rightSection={lookup.isPending ? <Loader size="xs" /> : null}
        autoComplete="off"
        spellCheck={false}
        visibleFrom="sm"
        w={280}
      />
    </form>
  );
}
