"use client";

import { ActionIcon, Loader, TextInput } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconBarcode, IconCamera } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useCan } from "@/components/MeProvider";
import { CameraScanner } from "@/components/scan/CameraScanner";
import { useScanLookup } from "@/hooks/use-scan-lookup";
import { Permission } from "@/lib/permissions";

/**
 * The "customer walks in with a phone" bar (FR-7.1, FR-7.2).
 *
 * The scanner does not know whether it read an IMEI off a handset or a
 * barcode off a box, so neither does this: one call goes out and the
 * server states which kind it found. It is also the only way into a
 * handset's page — a device unit is reached by its IMEI, never by a UUID
 * anyone could type.
 */

/** Dashboard idles as a scan station: pull focus back after this long of no other activity. */
const SCAN_REFOCUS_IDLE_MS = 2 * 60 * 1000;

export function ScanBar() {
  const t = useTranslations("scan");
  const pathname = usePathname();
  const can = useCan();
  const [code, setCode] = useState("");
  const [cameraOpened, { open: openCamera, close: closeCamera }] = useDisclosure(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const lookup = useScanLookup();

  const isDashboard = pathname === "/";
  const canScan = can(Permission.Scan.Lookup);

  // Kiosk behavior: on the dashboard, keep the scanner ready for the next
  // handset. It refocuses after idle time rather than on every blur, so it
  // doesn't yank focus away from someone actively typing elsewhere.
  useEffect(() => {
    if (!isDashboard || !canScan || cameraOpened) return;

    let idleTimer: ReturnType<typeof setTimeout>;
    const scheduleRefocus = () => {
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => {
        if (document.activeElement !== inputRef.current) {
          inputRef.current?.focus();
        }
      }, SCAN_REFOCUS_IDLE_MS);
    };

    inputRef.current?.focus();
    scheduleRefocus();
    document.addEventListener("mousedown", scheduleRefocus);
    document.addEventListener("keydown", scheduleRefocus);

    return () => {
      clearTimeout(idleTimer);
      document.removeEventListener("mousedown", scheduleRefocus);
      document.removeEventListener("keydown", scheduleRefocus);
    };
  }, [isDashboard, canScan, cameraOpened]);

  if (!canScan) return null;

  function onCameraDecode(scanned: string) {
    setCode(scanned);
    closeCamera();
    lookup.mutate(scanned, { onSuccess: () => setCode("") });
  }

  return (
    <>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const scanned = code.trim();
          if (scanned) lookup.mutate(scanned, { onSuccess: () => setCode("") });
        }}
      >
        <TextInput
          ref={inputRef}
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
      <ActionIcon
        variant="subtle"
        size="lg"
        aria-label={t("cameraTrigger")}
        hiddenFrom="sm"
        onClick={openCamera}
      >
        <IconCamera size={20} stroke={1.5} />
      </ActionIcon>
      <CameraScanner opened={cameraOpened} onClose={closeCamera} onDecode={onCameraDecode} />
    </>
  );
}
