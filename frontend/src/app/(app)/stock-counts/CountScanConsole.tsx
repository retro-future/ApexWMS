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

import { useCan } from "@/components/MeProvider";
import { MoneyInput } from "@/components/MoneyInput";
import { ProductSelect } from "@/components/ProductSelect";
import { CameraScanner } from "@/components/scan/CameraScanner";
import { useDocumentAction } from "@/hooks/use-document";
import { errorMessage } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import type { CountScanResult, Product, StockCount } from "@/lib/types";

type CountScanBody = {
  code: string;
  productId?: string;
  acquisitionCost?: string;
  unitCost?: string;
};

/**
 * One beep of the scanner onto an open count (PRD §6, FR-6.2).
 *
 * Two things separate this from the receipt's console. **There is no
 * condition picker**: a handset the store did not know it had enters `USED`
 * by construction, because `PriceResolver` refuses to quote a catalog price
 * for anything that is not `NEW`, and a settable condition would let a count
 * produce a surprise phone quoted at the new-goods price. And the response
 * is deliberately narrow — a count holds the whole shelf, so it names the one
 * row that changed plus the three running totals rather than re-sending
 * hundreds of rows per trigger pull.
 *
 * The product and cost fields are for a *surprise*: a handset with no row in
 * the store cannot be valued at confirm without them. They are only rendered
 * under `Pricing.Set`, and the cost key is omitted from the body entirely
 * rather than sent as null — the route escalates on the field being present,
 * so a null would be refused just as a figure would.
 *
 * `accessoryUnitCost` is the same idea for an accessory: only needed when
 * the location has never held that SKU before, so there is no pool average
 * to book a surplus at. It rides on every beep rather than only the first,
 * because the operator holding the scanner may not hold the pricing
 * permission and someone else may state it on a later pass.
 */
export function CountScanConsole({
  count,
  onScanned,
}: {
  count: StockCount;
  onScanned: (result: CountScanResult) => void;
}) {
  const t = useTranslations("stockCounts.scan");
  const tCommon = useTranslations("common");
  const can = useCan();
  const canPrice = can(Permission.Pricing.Set);

  const inputRef = useRef<HTMLInputElement>(null);
  const [code, setCode] = useState("");
  const [product, setProduct] = useState<Product | null>(null);
  const [cost, setCost] = useState("");
  const [accessoryUnitCost, setAccessoryUnitCost] = useState("");
  const [rejection, setRejection] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<string | null>(null);
  const [cameraOpened, { open: openCamera, close: closeCamera }] = useDisclosure(false);

  const scan = useDocumentAction<CountScanResult, CountScanBody>(
    "stock-counts",
    count.id,
    {
      path: "/scan",
      // The response carries the changed row and the running totals, so a
      // refetch between beeps would only spend the §6 latency budget.
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
      const result = await scan.mutateAsync({
        code: scanned,
        ...(canPrice && product ? { productId: product.id } : {}),
        // Never send the key without the permission: the route escalates on
        // the field being present, so a null is refused like a figure is.
        ...(canPrice && cost.trim() ? { acquisitionCost: cost.trim() } : {}),
        ...(canPrice && accessoryUnitCost.trim()
          ? { unitCost: accessoryUnitCost.trim() }
          : {}),
      });
      if (result) {
        onScanned(result);
        setAccepted(
          t("accepted", {
            code: scanned,
            matched: result.matchedCount,
            missing: result.missingCount,
            unexpected: result.unexpectedCount,
          }),
        );
      }
      setCode("");
      // The product and cost belong to the handset just scanned, not the next.
      setProduct(null);
      setCost("");
      setAccessoryUnitCost("");
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
          {/* The running totals after every beep (§6), so the operator never
              has to look away from the shelf to count the list. */}
          <Group gap="xs">
            <Badge size="sm" variant="light" color="teal">
              {t("matched", { count: count.matchedCount })}
            </Badge>
            <Badge size="sm" variant="light" color="orange">
              {t("missing", { count: count.missingCount })}
            </Badge>
            <Badge size="sm" variant="light" color="grape">
              {t("unexpected", { count: count.unexpectedCount })}
            </Badge>
          </Group>
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

            {canPrice && (
              <Group gap="sm" align="flex-end" wrap="wrap">
                <ProductSelect
                  label={t("surpriseProduct")}
                  value={product?.id ?? null}
                  onChange={(next) => {
                    setProduct(next);
                    // The cost was typed in the old product's currency.
                    setCost("");
                  }}
                  placeholder={t("surpriseProductHint")}
                />
                <MoneyInput
                  label={t("surpriseCost")}
                  description={t("surpriseCostHint")}
                  value={cost}
                  onChange={setCost}
                  currency={product?.currency}
                  disabled={product === null}
                  w={{ base: "100%", sm: 200 }}
                />
                <MoneyInput
                  label={t("accessoryCost")}
                  description={t("accessoryCostHint")}
                  value={accessoryUnitCost}
                  onChange={setAccessoryUnitCost}
                  w={{ base: "100%", sm: 200 }}
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
