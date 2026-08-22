"use client";

import {
  Alert,
  Center,
  Group,
  Loader,
  Pagination,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconAlertCircle, IconSearch } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { TableScrollArea } from "@/components/TableScrollArea";

/** Width of the trailing, unlabeled row-actions column shared by every list table. */
export const ACTIONS_COLUMN_WIDTH = 60;

/**
 * The frame every list page sits in: heading, search, filters, table,
 * pagination, and the loading / error / empty states that otherwise get
 * written four slightly different ways.
 */
export function ListShell({
  title,
  subtitle,
  action,
  search,
  filters,
  showInactive,
  onShowInactiveChange,
  head,
  children,
  isLoading,
  error,
  isEmpty,
  emptyMessage,
  total,
  page,
  pagesCount,
  onPageChange,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  search?: { value: string; onChange: (value: string) => void; placeholder: string };
  filters?: React.ReactNode;
  showInactive?: boolean;
  onShowInactiveChange?: (value: boolean) => void;
  head: React.ReactNode;
  children: React.ReactNode;
  isLoading: boolean;
  error?: unknown;
  isEmpty: boolean;
  /** For a list where empty is good news rather than a failed search. */
  emptyMessage?: string;
  total: number;
  /** Omit all three for an unpaged list — its endpoint returns every row at once. */
  page?: number;
  pagesCount?: number;
  onPageChange?: (page: number) => void;
}) {
  const t = useTranslations("common");

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <Stack gap="3xs">
          <Title order={2}>{title}</Title>
          {subtitle && (
            <Text size="sm" c="dimmed">
              {subtitle}
            </Text>
          )}
        </Stack>
        {action}
      </Group>

      <Group gap="sm" wrap="wrap" align="center">
        {search && (
          <TextInput
            value={search.value}
            onChange={(event) => search.onChange(event.currentTarget.value)}
            placeholder={search.placeholder}
            leftSection={<IconSearch size={16} stroke={1.5} />}
            w={{ base: "100%", sm: 280 }}
          />
        )}
        {filters}
        {onShowInactiveChange && (
          <Switch
            checked={Boolean(showInactive)}
            onChange={(event) =>
              onShowInactiveChange(event.currentTarget.checked)
            }
            label={t("showInactive")}
          />
        )}
      </Group>

      {error ? (
        <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
          {error instanceof Error ? error.message : t("retry")}
        </Alert>
      ) : (
        <TableScrollArea>
          <Table highlightOnHover verticalSpacing="sm" miw={640}>
            <Table.Thead>{head}</Table.Thead>
            <Table.Tbody>{children}</Table.Tbody>
          </Table>

          {isLoading && (
            <Center p="xl">
              <Loader size="sm" />
            </Center>
          )}

          {!isLoading && isEmpty && (
            <Center p="xl">
              <Stack gap="2xs" align="center">
                <Text fw={500}>{emptyMessage ?? t("noResults")}</Text>
                {!emptyMessage && (
                  <Text size="sm" c="dimmed">
                    {t("noResultsHint")}
                  </Text>
                )}
              </Stack>
            </Center>
          )}
        </TableScrollArea>
      )}

      <Group justify="space-between" wrap="wrap">
        <Text size="sm" c="dimmed">
          {t("totalItems", { count: total })}
        </Text>
        {pagesCount !== undefined && pagesCount > 1 && onPageChange && (
          <Pagination
            value={page ?? 1}
            onChange={onPageChange}
            total={pagesCount}
            size="sm"
          />
        )}
      </Group>
    </Stack>
  );
}
