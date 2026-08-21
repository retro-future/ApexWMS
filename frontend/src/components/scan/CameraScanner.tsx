"use client";

import { Alert, Button, Loader, Modal, Stack, Text } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { BrowserMultiFormatReader, type IScannerControls } from "@zxing/browser";
import { BarcodeFormat, DecodeHintType } from "@zxing/library";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import classes from "@/components/scan/CameraScanner.module.css";

type ErrorState = "insecure" | "denied" | "noCamera" | "unsupported" | "error";
type ScannerState = "starting" | "scanning" | ErrorState;

const HINTS = new Map<DecodeHintType, unknown>([
  [
    DecodeHintType.POSSIBLE_FORMATS,
    [
      BarcodeFormat.CODE_128,
      BarcodeFormat.EAN_13,
      BarcodeFormat.EAN_8,
      BarcodeFormat.UPC_A,
      BarcodeFormat.UPC_E,
      BarcodeFormat.CODE_39,
    ],
  ],
  [DecodeHintType.TRY_HARDER, true],
]);

// One lingering camera frame can decode the same barcode several times in a
// row; ignore repeats within this window instead of submitting it twice.
const DUPLICATE_WINDOW_MS = 1500;

function classifyError(error: unknown): ErrorState {
  if (error instanceof ScanEnvironmentError) return error.state;
  const name = error instanceof DOMException ? error.name : undefined;
  if (name === "NotAllowedError" || name === "PermissionDeniedError") return "denied";
  if (
    name === "NotFoundError" ||
    name === "DevicesNotFoundError" ||
    name === "OverconstrainedError"
  ) {
    return "noCamera";
  }
  return "error";
}

/** Thrown to short-circuit the decode promise chain before the camera ever opens. */
class ScanEnvironmentError extends Error {
  constructor(readonly state: ErrorState) {
    super(state);
  }
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
  const videoRef = useRef<HTMLVideoElement>(null);
  const controlsRef = useRef<IScannerControls | null>(null);
  const lastDecodeRef = useRef<{ code: string; at: number } | null>(null);
  // Read inside the decode callback without retriggering the effect below
  // every time the caller passes a fresh onDecode closure.
  const onDecodeRef = useRef(onDecode);
  useEffect(() => {
    onDecodeRef.current = onDecode;
  });

  const [state, setState] = useState<ScannerState>("starting");

  useEffect(() => {
    if (!opened) return;

    let cancelled = false;

    Promise.resolve()
      .then(() => {
        if (!window.isSecureContext) throw new ScanEnvironmentError("insecure");
        if (!navigator.mediaDevices?.getUserMedia) {
          throw new ScanEnvironmentError("unsupported");
        }
        setState("starting");
        const reader = new BrowserMultiFormatReader(HINTS);
        return reader.decodeFromConstraints(
          { video: { facingMode: "environment" } },
          videoRef.current ?? undefined,
          (result) => {
            if (!result) return;
            const code = result.getText();
            const now = Date.now();
            const last = lastDecodeRef.current;
            if (last && last.code === code && now - last.at < DUPLICATE_WINDOW_MS) return;
            lastDecodeRef.current = { code, at: now };
            onDecodeRef.current(code);
          },
        );
      })
      .then((controls) => {
        if (cancelled) {
          controls.stop();
          return;
        }
        controlsRef.current = controls;
        setState("scanning");
      })
      .catch((error: unknown) => {
        if (!cancelled) setState(classifyError(error));
      });

    return () => {
      cancelled = true;
      controlsRef.current?.stop();
      controlsRef.current = null;
      lastDecodeRef.current = null;
    };
  }, [opened]);

  const isVideoState = state === "starting" || state === "scanning";

  return (
    <Modal opened={opened} onClose={onClose} title={title ?? t("title")} centered>
      <Stack gap="md">
        <div style={{ display: isVideoState ? "block" : "none" }}>
          <video ref={videoRef} muted playsInline className={classes.video} />
          {state === "starting" && (
            <Stack align="center" gap="xs" mt="sm">
              <Loader size="sm" />
              <Text size="sm" c="dimmed">
                {t("starting")}
              </Text>
            </Stack>
          )}
        </div>

        {!isVideoState && (
          <Alert
            variant="light"
            color="red"
            icon={<IconAlertCircle size={18} stroke={1.5} />}
            role="alert"
          >
            {t(state)}
          </Alert>
        )}

        <Button variant="default" onClick={onClose}>
          {t("close")}
        </Button>
      </Stack>
    </Modal>
  );
}
