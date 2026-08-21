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
import { formatMoney } from "@/lib/money";
import { errorMessage } from "@/lib/notify";
import type { InvoiceScanResult, SalesInvoice } from "@/lib/types";

/**
 * One beep of the scanner at the till (PRD §6, FR-4.2).
 *
 * The scanner is a keyboard wedge: it types the code into whatever has
 * focus and presses Enter. So the input keeps focus at all times, clears
 * itself after every accepted scan, and never sits behind a modal.
 *
 * **The client sends the raw string and nothing else.** It does not decide
 * whether it read an IMEI off a handset or a barcode off a box — the
 * operator's scanner does not know, and neither does this. The server
 * states which it found (FR-7.1).
 *
 * A rejection stays on screen until the next scan replaces it, shown
 * verbatim. The server's messages are the point of this screen: a handset
 * that is already sold names its actual status (FR-4.3), one held at
 * another location says so (FR-4.4), and an unpriced used phone is refused
 * outright with a message naming an Owner or Manager, because the Seller
 * reading it cannot fix it themselves (FR-4.2b).
 */
export function SellConsole({
  invoice,
  onScanned,
}: {
  invoice: SalesInvoice;
  onScanned: (result: InvoiceScanResult) => void;
}) {
  const t = useTranslations("invoices.sell");
  const tCommon = useTranslations("common");

  const inputRef = useRef<HTMLInputElement>(null);
  const [code, setCode] = useState("");
  const [rejection, setRejection] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<string | null>(null);
  const [cameraOpened, { open: openCamera, close: closeCamera }] = useDisclosure(false);

  const scan = useDocumentAction<InvoiceScanResult, { code: string }>(
    "invoices",
    invoice.id,
    {
      path: "/scan",
      // The response carries the line and the running count, so a refetch
      // between beeps would only spend the §6 latency budget.
      invalidate: false,
    },
  );

  // The wedge types wherever the caret is; keep it here.
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function submitCode(raw: string) {
    const scanned = raw.trim();
    if (!scanned) return;

    setRejection(null);
    try {
      const result = await scan.mutateAsync({ code: scanned });
      if (result) {
        onScanned(result);
        setAccepted(
          t("accepted", {
            price: formatMoney(result.resolvedPriceMinor, result.line.currency),
            count: result.lineCount,
          }),
        );
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
            {t("lineCount", { count: invoice.lines.length })}
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
