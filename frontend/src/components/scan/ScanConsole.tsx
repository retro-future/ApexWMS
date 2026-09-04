"use client";

import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconAlertCircle, IconBarcode, IconCamera } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { CameraScanner } from "@/components/scan/CameraScanner";
import { useDocumentAction } from "@/hooks/use-document";
import { errorMessage } from "@/lib/notify";
import type { Removal, RemovalResource } from "@/lib/removals";

/**
 * One beep of the scanner onto a supplier return or a write-off (PRD §6).
 *
 * One console for both, because both endpoints take `{ code }` and answer
 * with the whole document — the two differ in what confirming them *means*,
 * not in what a scan says.
 *
 * The scanner is a keyboard wedge: it types the code into whatever has focus
 * and presses Enter. So the input keeps focus at all times, clears itself
 * after every accepted scan, and never sits behind a modal.
 *
 * A rejection stays on screen until the next scan replaces it, verbatim. The
 * server's message is the point: FR-5.2 names the handset's actual status
 * when it is not on the shelf, and a phone held elsewhere says so — a
 * paraphrase would cost the operator the one fact they need.
 */
export function RemovalScanConsole<T extends Removal>({
  resource,
  document,
  onScanned,
}: {
  resource: RemovalResource;
  document: T;
  onScanned: (updated: T) => void;
}) {
  const t = useTranslations(
    resource === "supplier-returns" ? "supplierReturns.scan" : "writeOffs.scan",
  );
  const tCommon = useTranslations("common");

  const inputRef = useRef<HTMLInputElement>(null);
  const [code, setCode] = useState("");
  const [rejection, setRejection] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<string | null>(null);
  const [cameraOpened, { open: openCamera, close: closeCamera }] = useDisclosure(false);

  const scan = useDocumentAction<T, { code: string }>(resource, document.id, {
    path: "/scan",
    // The response is the whole refreshed document, so a refetch between
    // beeps would only spend the §6 latency budget.
    invalidate: false,
  });

  // The wedge types wherever the caret is; keep it here.
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function submitCode(raw: string) {
    const scanned = raw.trim();
    if (!scanned) return;

    setRejection(null);
    try {
      const updated = await scan.mutateAsync({ code: scanned });
      if (updated) {
        onScanned(updated);
        setAccepted(t("accepted", { code: scanned, count: updated.lineCount }));
      }
      setCode("");
    } catch (error) {
      setAccepted(null);
      setRejection(errorMessage(error, tCommon("retry")));
      // Keep the bad code visible so the operator can see what was read.
      inputRef.current?.select();
    } finally {
      inputRef.current?.focus();
    }
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitCode(code);
  }

  function onCameraDecode(decoded: string) {
    setCode(decoded);
    void submitCode(decoded);
  }

  return (
    <Card withBorder radius="md" padding="lg">
      <Stack gap="md">
        <Group justify="space-between" align="flex-end" wrap="wrap">
          <Text fw={500}>{t("title")}</Text>
          <Badge size="sm" variant="light">
            {t("lineCount", { count: document.lineCount })}
          </Badge>
        </Group>

        <form onSubmit={submit} noValidate>
          <Stack gap="md">
            <Group gap="sm" align="flex-end" wrap="wrap">
              <TextInput
                ref={inputRef}
                value={code}
                onChange={(event) => setCode(event.currentTarget.value)}
                label={t("placeholder")}
                description={t("hint")}
                leftSection={<IconBarcode size={18} stroke={1.5} />}
                autoComplete="off"
                spellCheck={false}
                w={{ base: "100%", sm: 320 }}
                aria-label={t("placeholder")}
              />
              <Button type="submit" loading={scan.isPending}>
                {t("title")}
              </Button>
              <ActionIcon
                variant="default"
                size="lg"
                aria-label={t("cameraTrigger")}
                onClick={openCamera}
              >
                <IconCamera size={20} stroke={1.5} />
              </ActionIcon>
            </Group>

            {rejection && (
              <Alert
                variant="light"
                color="red"
                icon={<IconAlertCircle size={18} />}
                role="alert"
              >
                {rejection}
              </Alert>
            )}

            {!rejection && accepted && (
              <Text size="sm" c="teal">
                {accepted}
              </Text>
            )}
          </Stack>
          <CameraScanner
            opened={cameraOpened}
            onClose={closeCamera}
            onDecode={onCameraDecode}
            title={t("title")}
          />
        </form>
      </Stack>
    </Card>
  );
}
