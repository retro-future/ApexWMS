"use client";

import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Select,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { IconAlertCircle, IconBarcode, IconCheck } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { useCan } from "@/components/MeProvider";
import { useDocumentAction } from "@/hooks/use-document";
import { useProductLookup } from "@/hooks/use-lookup";
import { formatMoney, minorToInput } from "@/lib/money";
import { errorMessage } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import { isSerial, scanProgress, type ReferenceCost } from "@/lib/receipts";
import type {
  Currency,
  DeviceCondition,
  GoodsReceipt,
  ScanResult,
} from "@/lib/types";

const CONDITIONS: DeviceCondition[] = ["new", "refurbished", "used"];

type ScanBody = {
  imei: string;
  lineId?: string;
  condition: DeviceCondition;
  acquisitionCost?: string;
  askingPrice?: string;
  cashPaid?: string;
  cashPaidCurrency?: Currency;
};

/**
 * One beep of the scanner, and the screen that surrounds it (PRD §6).
 *
 * The scanner is a keyboard wedge: it types the code into whatever has
 * focus and presses Enter. So the input keeps focus at all times, clears
 * itself after every accepted scan, and never sits behind a modal — a
 * dialog stealing focus mid-delivery breaks the workflow far more
 * thoroughly than a slow request would.
 *
 * A rejection stays on screen until the next scan replaces it. The server's
 * message already names what is wrong (the existing unit's status and
 * location for a duplicate, the Luhn failure for a mis-scan), so it is
 * shown verbatim rather than paraphrased into something vaguer.
 */
export function ScanConsole({
  receipt,
  referenceCosts,
  onScanned,
}: {
  receipt: GoodsReceipt;
  referenceCosts: Map<string, ReferenceCost>;
  onScanned: (result: ScanResult) => void;
}) {
  const t = useTranslations("receipts.scan");
  const tDoc = useTranslations("documents");
  const tCommon = useTranslations("common");
  const can = useCan();
  const canPrice = can(Permission.Pricing.Set);
  const products = useProductLookup();
  const queryClient = useQueryClient();

  const inputRef = useRef<HTMLInputElement>(null);
  const [code, setCode] = useState("");
  const [condition, setCondition] = useState<DeviceCondition>("new");
  // null means "untouched" — the field then shows the PO's reference cost
  // (if any) for whatever line is selected, without that default ever being
  // committed to state until the operator actually edits it.
  const [costInput, setCostInput] = useState<string | null>(null);
  const [askingPrice, setAskingPrice] = useState("");
  const [cashPaid, setCashPaid] = useState("");
  const [rejection, setRejection] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<string | null>(null);

  const serialLines = receipt.lines.filter(isSerial);
  // A scan onto a receipt with several serialized lines must name one, so
  // the console picks the first line still short of its count rather than
  // letting the first beep fail on a question the operator did not answer.
  const [lineId, setLineId] = useState<string | null>(
    (serialLines.find((line) => !scanProgress(line).isComplete) ?? serialLines[0])
      ?.id ?? null,
  );

  // Lines that still need scans, recomputed every render straight off the
  // (fresh, post-scan) receipt prop — this is what lets a line that just
  // filled up stop being offered without an effect writing state back.
  const incompleteLines = serialLines.filter((line) => !scanProgress(line).isComplete);
  const allScanned = serialLines.length > 0 && incompleteLines.length === 0;

  const scan = useDocumentAction<ScanResult, ScanBody>("receipts", receipt.id, {
    path: "/scan",
    // The response carries the accepted unit and the running count, so a
    // refetch between beeps would only spend the §6 latency budget.
    invalidate: false,
  });

  // The wedge types wherever the caret is; keep it here.
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // `lineId` is the operator's last explicit pick. It stays honored as
  // long as that line still needs scans; the moment it fills up (or was
  // never a real choice), the active line falls back to the first one
  // still short — the same "state is the override, not the source of
  // truth" shape as costInput/cost below, just for line selection.
  const activeLineId =
    (lineId && incompleteLines.some((line) => line.id === lineId)
      ? lineId
      : incompleteLines[0]?.id) ?? null;

  const selectedLine = serialLines.find((line) => line.id === activeLineId);
  const reference = selectedLine
    ? referenceCosts.get(selectedLine.productId)
    : undefined;
  const cost =
    costInput ?? (reference ? minorToInput(reference.minor, reference.currency) : "");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const imei = code.trim();
    if (!imei) return;

    setRejection(null);
    try {
      const result = await scan.mutateAsync({
        imei,
        ...(activeLineId ? { lineId: activeLineId } : {}),
        condition,
        // Money is sent only by someone who may state it; sending these
        // fields at all escalates the route's permission (FR-3.4b).
        ...(canPrice && cost.trim() ? { acquisitionCost: cost.trim() } : {}),
        ...(canPrice && askingPrice.trim()
          ? { askingPrice: askingPrice.trim() }
          : {}),
        ...(canPrice && cashPaid.trim()
          ? { cashPaid: cashPaid.trim(), cashPaidCurrency: "UZS" as Currency }
          : {}),
      });
      if (result) {
        onScanned(result);
        setAccepted(
          t("accepted", {
            imei: result.unit.imei,
            scanned: result.scannedCount,
            expected: result.expectedCount,
          }),
        );

        // The cached subtotals are frozen since page load (invalidate:
        // false above) — refetch once the receipt has nothing left to
        // scan, instead of on every beep, so the total is right without
        // paying a round trip per handset.
        const completesReceipt =
          result.scannedCount >= result.expectedCount &&
          serialLines.every(
            (line) => line.id === result.lineId || scanProgress(line).isComplete,
          );
        if (completesReceipt) {
          queryClient.invalidateQueries({ queryKey: ["receipts"] });
        }
      }
      setCode("");
      // Per-handset money belongs to the handset just scanned, not the next —
      // back to "untouched" so the field falls back to the PO's reference
      // cost again, rather than blanking a run of identical phones.
      setCostInput(null);
      setAskingPrice("");
      setCashPaid("");
    } catch (error) {
      setAccepted(null);
      setRejection(errorMessage(error, tCommon("retry")));
      // Keep the bad code visible so the operator can see what was read.
      inputRef.current?.select();
    } finally {
      inputRef.current?.focus();
    }
  }

  return (
    <Card withBorder radius="md" padding="lg">
      <Stack gap="md">
        <Group justify="space-between" align="flex-end" wrap="wrap">
          <Text fw={500}>{t("title")}</Text>
          {/* The running count after every beep, per line (§6). */}
          <Group gap="xs">
            {serialLines.map((line) => {
              const progress = scanProgress(line);
              return (
                <Badge
                  key={line.id}
                  size="sm"
                  variant={line.id === activeLineId ? "filled" : "light"}
                  color={progress.isComplete ? "teal" : "gray"}
                >
                  {products.get(line.productId) ?? tCommon("none")}{" "}
                  {progress.scanned}/{progress.expected}
                </Badge>
              );
            })}
          </Group>
        </Group>

        {allScanned ? (
          <Alert variant="light" color="teal" icon={<IconCheck size={18} stroke={1.5} />}>
            {t("allScanned")}
          </Alert>
        ) : (
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

                {incompleteLines.length > 1 && (
                  <Select
                    label={t("line")}
                    value={activeLineId}
                    onChange={setLineId}
                    data={incompleteLines.map((line) => ({
                      value: line.id,
                      label: `${products.get(line.productId) ?? "—"} · ${line.scannedCount}/${line.quantity}`,
                    }))}
                    w={{ base: "100%", sm: 220 }}
                  />
                )}

                <Select
                  label={t("condition")}
                  description={t("conditionHint")}
                  value={condition}
                  onChange={(value) => setCondition((value ?? "new") as DeviceCondition)}
                  data={CONDITIONS.map((value) => ({
                    value,
                    label: tDoc(`condition.${value}`),
                  }))}
                  w={{ base: "100%", sm: 180 }}
                  allowDeselect={false}
                />

                <Button type="submit" loading={scan.isPending}>
                  {t("title")}
                </Button>
              </Group>

              {canPrice && (
                <Group gap="sm" align="flex-end" wrap="wrap">
                  <TextInput
                    label={t("acquisitionCost")}
                    description={
                      reference
                        ? t("poReferenceHint", {
                            price: formatMoney(reference.minor, reference.currency),
                          })
                        : undefined
                    }
                    value={cost}
                    onChange={(event) => setCostInput(event.currentTarget.value)}
                    w={{ base: "100%", sm: 160 }}
                  />
                  <TextInput
                    label={t("askingPrice")}
                    value={askingPrice}
                    onChange={(event) => setAskingPrice(event.currentTarget.value)}
                    w={{ base: "100%", sm: 160 }}
                  />
                  <TextInput
                    label={t("cashPaid")}
                    description={t("cashPaidHint")}
                    value={cashPaid}
                    onChange={(event) => setCashPaid(event.currentTarget.value)}
                    rightSection={
                      <Text size="xs" c="dimmed">
                        UZS
                      </Text>
                    }
                    rightSectionWidth={44}
                    w={{ base: "100%", sm: 260 }}
                  />
                </Group>
              )}

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
          </form>
        )}
      </Stack>
    </Card>
  );
}
