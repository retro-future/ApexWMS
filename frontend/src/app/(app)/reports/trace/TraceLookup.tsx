"use client";

import { Button, Card, Group, Stack, Text, TextInput, Title } from "@mantine/core";
import { IconSearch } from "@tabler/icons-react";
import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { DeviceTraceTimeline } from "@/components/DeviceTraceTimeline";
import { ErrorAlert } from "@/components/ErrorAlert";
import { apiGet, queryString } from "@/lib/api";
import { errorMessage } from "@/lib/notify";
import type { DeviceUnit, ScanLookup } from "@/lib/types";

/**
 * FR-9.2 from an IMEI rather than from a unit page: *"a customer returns a
 * phone claiming they bought it here"*.
 *
 * The code goes through `GET /scan/lookup`, so a scanner pointed at the
 * label reaches the same trace as a typed IMEI — the field takes whichever
 * arrives. A barcode that names a product rather than a handset is answered
 * plainly instead of a blank timeline.
 */
export function TraceLookup() {
  const t = useTranslations("reports");
  const tScan = useTranslations("scan");
  const tCommon = useTranslations("common");

  const [code, setCode] = useState("");
  const [unit, setUnit] = useState<DeviceUnit | null>(null);
  const [error, setError] = useState<string | null>(null);

  const lookup = useMutation({
    mutationFn: (value: string) =>
      apiGet<ScanLookup>(`/scan/lookup${queryString({ code: value })}`),
  });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const value = code.trim();
    if (!value) return;

    try {
      const result = await lookup.mutateAsync(value);
      if (result.kind === "device" && result.device) {
        setUnit(result.device);
      } else {
        setUnit(null);
        setError(t("traceNotADevice"));
      }
    } catch (thrown) {
      setUnit(null);
      setError(errorMessage(thrown, tScan("notFound", { code: value })));
    }
  }

  return (
    <Stack gap="lg">
      <Stack gap="3xs">
        <Title order={2}>{t("traceTitle")}</Title>
        <Text size="sm" c="dimmed">
          {t("traceSubtitle")}
        </Text>
      </Stack>

      <form onSubmit={submit}>
        <Group gap="sm" align="flex-end" wrap="wrap">
          <TextInput
            label={t("imei")}
            value={code}
            onChange={(event) => setCode(event.currentTarget.value)}
            placeholder={tScan("placeholder")}
            leftSection={<IconSearch size={16} stroke={1.5} />}
            w={{ base: "100%", sm: 320 }}
            autoFocus
          />
          <Button type="submit" loading={lookup.isPending}>
            {tCommon("search")}
          </Button>
        </Group>
      </form>

      <ErrorAlert message={error} />

      {unit && (
        <Card withBorder radius="md" padding="lg">
          <Stack gap="md">
            <Stack gap="3xs">
              <Text fw={600} ff="monospace">
                {unit.imei}
              </Text>
              <Text size="sm" c="dimmed">
                {unit.productName}
              </Text>
            </Stack>
            <DeviceTraceTimeline deviceUnitId={unit.id} />
          </Stack>
        </Card>
      )}
    </Stack>
  );
}
