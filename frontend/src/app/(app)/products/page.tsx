"use client";

import {
  ActionIcon,
  Anchor,
  Badge,
  Button,
  Group,
  Select,
  Stack,
  Table,
  Text,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconPencil, IconPlus } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import { useCan } from "@/components/MeProvider";
import { ACTIONS_COLUMN_WIDTH, ListShell } from "@/components/ListShell";
import { StatusBadge } from "@/components/StatusBadge";
import { makePageReset, useResourceList } from "@/hooks/use-resource";
import { formatMoney } from "@/lib/money";
import { Permission } from "@/lib/permissions";
import type { Product } from "@/lib/types";

export default function ProductsPage() {
  const t = useTranslations("products");
  const tCommon = useTranslations("common");
  const can = useCan();

  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [showInactive, setShowInactive] = useState(false);
  const [tracking, setTracking] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const reset = makePageReset(setPage);

  const query = useResourceList<Product>("products", {
    page,
    search: debouncedSearch || undefined,
    isActive: showInactive ? undefined : true,
    trackingType: tracking ?? undefined,
  });

  const products = query.data?.items ?? [];

  return (
    <ListShell
      title={t("title")}
      subtitle={t("subtitle")}
      action={
        can(Permission.Catalog.Manage) && (
          <Button
            component={Link}
            href="/products/new"
            leftSection={<IconPlus size={16} />}
          >
            {t("new")}
          </Button>
        )
      }
      search={{
        value: search,
        onChange: reset(setSearch),
        placeholder: t("searchPlaceholder"),
      }}
      filters={
        <Select
          value={tracking}
          onChange={reset(setTracking)}
          placeholder={t("filterTracking")}
          clearable
          w={{ base: "100%", sm: 180 }}
          data={[
            { value: "serial", label: t("serial") },
            { value: "quantity", label: t("quantity") },
          ]}
        />
      }
      showInactive={showInactive}
      onShowInactiveChange={reset(setShowInactive)}
      isLoading={query.isLoading}
      error={query.error}
      isEmpty={products.length === 0}
      total={query.data?.totalItems ?? 0}
      page={page}
      pagesCount={query.data?.pagesCount ?? 0}
      onPageChange={setPage}
      head={
        <Table.Tr>
          <Table.Th>{t("sku")}</Table.Th>
          <Table.Th>{t("name")}</Table.Th>
          <Table.Th>{t("trackingType")}</Table.Th>
          <Table.Th>{t("price")}</Table.Th>
          <Table.Th>{tCommon("status")}</Table.Th>
          <Table.Th w={ACTIONS_COLUMN_WIDTH} />
        </Table.Tr>
      }
    >
      {products.map((product) => (
        <Table.Tr key={product.id}>
          <Table.Td>
            <Text ff="monospace" size="sm">
              {product.sku}
            </Text>
          </Table.Td>
          <Table.Td>
            <Stack gap={0}>
              <Anchor
                component={Link}
                href={`/products/${product.id}`}
                size="sm"
                fw={500}
              >
                {product.name}
              </Anchor>
              {(product.brand || product.model) && (
                <Text size="xs" c="dimmed">
                  {[product.brand, product.model].filter(Boolean).join(" · ")}
                </Text>
              )}
            </Stack>
          </Table.Td>
          <Table.Td>
            <Badge
              size="sm"
              variant="light"
              color={product.trackingType === "serial" ? "grape" : "blue"}
            >
              {product.trackingType === "serial" ? t("serial") : t("quantity")}
            </Badge>
          </Table.Td>
          <Table.Td>
            {product.defaultSalePrice === null ? (
              <Text c="dimmed">{tCommon("none")}</Text>
            ) : (
              <Text size="sm">
                {formatMoney(product.defaultSalePrice)}
              </Text>
            )}
          </Table.Td>
          <Table.Td>
            <StatusBadge isActive={product.isActive} />
          </Table.Td>
          <Table.Td>
            <Group justify="flex-end">
              <ActionIcon
                component={Link}
                href={`/products/${product.id}`}
                variant="subtle"
                aria-label={tCommon("edit")}
              >
                <IconPencil size={16} />
              </ActionIcon>
            </Group>
          </Table.Td>
        </Table.Tr>
      ))}
    </ListShell>
  );
}
