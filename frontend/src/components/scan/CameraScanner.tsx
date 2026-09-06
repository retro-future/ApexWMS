"use client";

import { Alert, Button, Loader, Modal, Stack, Text } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import {
  boundingBox,
  prepareZXingModule,
  Scanner,
  type IDetectedBarcode,
  type IScannerError,
  type IScannerHandle,
  type IScannerProps,
} from "@yudiel/react-qr-scanner";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

type ErrorState = "insecure" | "denied" | "noCamera" | "unsupported" | "error";

const FORMATS: NonNullable<IScannerProps["formats"]> = [
  "code_128",
  "ean_13",
  "ean_8",
  "upc_a",
  "upc_e",
  "code_39",
];

// One lingering camera frame can decode the same barcode several times in a
// row; ignore repeats within this window instead of submitting it twice.
const DUPLICATE_WINDOW_MS = 1500;

// Android Chrome decodes with the native BarcodeDetector, so a short retry
// gap costs little and is what makes a dense IMEI Code 128 lock on quickly.
const RETRY_DELAY_MS = 50;

// A 640x480 default resolution blurs the bars of a dense Code 128 together, and
// without continuous focus the camera keeps hunting past the label. `focusMode`
// is not in the standard MediaTrackConstraintSet type but Android Chrome honours
// it, and a browser that doesn't just ignores the advanced entry.
const CONSTRAINTS: MediaTrackConstraints = {
  facingMode: "environment",
  width: { ideal: 1920 },
  height: { ideal: 1080 },
  advanced: [{ focusMode: "continuous" } as MediaTrackConstraintSet],
};

// The scanner merges these over its own inline styles, so a CSS class would
// lose to them.
const SCANNER_STYLES = {
  container: {
    height: "auto",
    aspectRatio: "4 / 3",
    borderRadius: "var(--mantine-radius-md)",
    backgroundColor: "var(--mantine-color-dark-8)",
  },
};

// Serve the wasm ourselves so an iPhone, which has no native BarcodeDetector,
// does not have to reach jsDelivr to scan. See scripts/copy-zxing-wasm.mjs.
prepareZXingModule({
  overrides: {
    locateFile: (path: string, prefix: string) =>
      path.endsWith(".wasm") ? "/wasm/zxing_reader.wasm" : `${prefix}${path}`,
  },
});

function classifyError(error: IScannerError): ErrorState {
  switch (error.kind) {
    case "permission-denied":
      return "denied";
    case "no-camera":
    case "overconstrained":
      return "noCamera";
    case "insecure-context":
      return "insecure";
    case "unsupported":
      return "unsupported";
    default:
      return "error";
  }
}

function environmentError(): ErrorState | null {
  if (typeof window === "undefined") return null;
  if (!window.isSecureContext) return "insecure";
  if (!navigator.mediaDevices?.getUserMedia) return "unsupported";
  return null;
}

/**
 * Camera-based alternative to the keyboard-wedge scan inputs, for a phone
 * with no hardware scanner attached. Owns only the camera lifecycle and
 * decode loop — the caller decides what a decoded code means and whether to
 * close the modal after one.
 */
export function CameraScanner({
  opened,
  onClose,
  onDecode,
  title,
}: {
  opened: boolean;
  onClose: () => void;
  onDecode: (code: string) => void;
  title?: string;
}) {
  const t = useTranslations("camera");

  return (
    <Modal opened={opened} onClose={onClose} title={title ?? t("title")} centered>
      <Stack gap="md">
        <ScannerView onDecode={onDecode} />
        <Button variant="default" onClick={onClose}>
          {t("close")}
        </Button>
      </Stack>
    </Modal>
  );
}

/**
 * Split out so closing the modal unmounts it: that stops the camera track and
 * clears the error and duplicate state without any reset logic.
 */
function ScannerView({ onDecode }: { onDecode: (code: string) => void }) {
  const t = useTranslations("camera");
  const [error, setError] = useState<ErrorState | null>(environmentError);
  const [playing, setPlaying] = useState(false);
  const handleRef = useRef<IScannerHandle>(null);
  const lastDecodeRef = useRef<{ code: string; at: number } | null>(null);

  useEffect(() => {
    const video = handleRef.current?.getVideoElement();
    if (!video) return;
    const markPlaying = () => setPlaying(true);
    video.addEventListener("playing", markPlaying);
    return () => video.removeEventListener("playing", markPlaying);
  }, []);

  function handleScan(codes: IDetectedBarcode[]) {
    const code = codes[0]?.rawValue;
    if (!code) return;
    const now = Date.now();
    const last = lastDecodeRef.current;
    if (last && last.code === code && now - last.at < DUPLICATE_WINDOW_MS) return;
    lastDecodeRef.current = { code, at: now };
    onDecode(code);
  }

  if (error) {
    return (
      <Alert
        variant="light"
        color="red"
        icon={<IconAlertCircle size={18} stroke={1.5} />}
        role="alert"
      >
        {t(error)}
      </Alert>
    );
  }

  return (
    <div>
      <Scanner
        ref={handleRef}
        onScan={handleScan}
        onError={(scanError) => setError(classifyError(scanError))}
        formats={FORMATS}
        constraints={CONSTRAINTS}
        components={{ finder: true, torch: true, tracker: boundingBox }}
        retryDelay={RETRY_DELAY_MS}
        allowMultiple={false}
        sound={false}
        styles={SCANNER_STYLES}
      />
      {!playing && (
        <Stack align="center" gap="xs" mt="sm">
          <Loader size="sm" />
          <Text size="sm" c="dimmed">
            {t("starting")}
          </Text>
        </Stack>
      )}
    </div>
  );
}
