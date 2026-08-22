"use client";

import {
  ActionIcon,
  Button,
  Group,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { IconPencil, IconPlus } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { FormModal } from "@/components/FormModal";
import { ACTIONS_COLUMN_WIDTH, ListShell } from "@/components/ListShell";
import { useCan } from "@/components/MeProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { useCrudEntityList } from "@/hooks/use-crud-entity-list";
import { Permission } from "@/lib/permissions";
import type { Supplier } from "@/lib/types";

type Values = {
  name: string;
  contactName: string;
  phone: string;
  email: string;
  isActive: boolean;
};

const EMPTY: Values = {
  name: "",
  contactName: "",
  phone: "",
  email: "",
  isActive: true,
};

export default function SuppliersPage() {
  const t = useTranslations("suppliers");
  const tCommon = useTranslations("common");
  const can = useCan();
  // Suppliers have no permission module of their own — PRD §2.1 lumps them
  // in with the catalog ("manage catalog (products, suppliers)").
  const manage = can(Permission.Catalog.Manage);

  const form = useForm<Values>({
    initialValues: EMPTY,
    validate: {
      name: (value) => (value.trim() ? null : tCommon("required")),
      email: (value) =>
        !value.trim() || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value.trim())
          ? null
          : t("email"),
    },
  });

  const list = useCrudEntityList<Supplier, Values>("suppliers", form, {
    empty: EMPTY,
    toValues: (supplier) => ({
      name: supplier.name,
      contactName: supplier.contactName ?? "",
      phone: supplier.phone ?? "",
      email: supplier.email ?? "",
      isActive: supplier.isActive,
    }),
    toPayload: (values) => ({
      name: values.name.trim(),
      contactName: values.contactName.trim() || null,
      phone: values.phone.trim() || null,
      email: values.email.trim() || null,
    }),
    conflictField: "name",
  });

  return (
    <>
      <ListShell
        title={t("title")}
        subtitle={t("subtitle")}
        action={
          manage && (
            <Button leftSection={<IconPlus size={16} />} onClick={() => list.open(null)}>
              {t("new")}
            </Button>
          )
        }
        search={{
          value: list.search,
          onChange: list.onSearchChange,
          placeholder: t("searchPlaceholder"),
        }}
        showInactive={list.showInactive}
        onShowInactiveChange={list.onShowInactiveChange}
        isLoading={list.isLoading}
        error={list.error}
        isEmpty={list.items.length === 0}
        total={list.total}
        page={list.page}
        pagesCount={list.pagesCount}
        onPageChange={list.setPage}
        head={
          <Table.Tr>
            <Table.Th>{t("name")}</Table.Th>
            <Table.Th>{t("contactName")}</Table.Th>
            <Table.Th>{t("phone")}</Table.Th>
            <Table.Th>{tCommon("status")}</Table.Th>
            <Table.Th w={ACTIONS_COLUMN_WIDTH} />
          </Table.Tr>
        }
      >
        {list.items.map((supplier) => (
          <Table.Tr key={supplier.id}>
            <Table.Td>
              <Stack gap={0}>
                <Text size="sm" fw={500}>
                  {supplier.name}
                </Text>
                {supplier.email && (
                  <Text size="xs" c="dimmed">
                    {supplier.email}
                  </Text>
                )}
              </Stack>
            </Table.Td>
            <Table.Td>
              <Text size="sm" c={supplier.contactName ? undefined : "dimmed"}>
                {supplier.contactName ?? tCommon("none")}
              </Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm" c={supplier.phone ? undefined : "dimmed"}>
                {supplier.phone ?? tCommon("none")}
              </Text>
            </Table.Td>
            <Table.Td>
              <StatusBadge isActive={supplier.isActive} />
            </Table.Td>
            <Table.Td>
              <Group justify="flex-end">
                {manage && (
                  <ActionIcon
                    variant="subtle"
                    aria-label={tCommon("edit")}
                    onClick={() => list.open(supplier)}
                  >
                    <IconPencil size={16} />
                  </ActionIcon>
                )}
              </Group>
            </Table.Td>
          </Table.Tr>
        ))}
      </ListShell>

      <FormModal
        opened={list.opened}
        onClose={list.closeModal}
        title={list.editing ? t("editTitle") : t("newTitle")}
        onSubmit={form.onSubmit(list.submit)}
        busy={list.busy}
        error={list.formError}
        submitLabel={list.editing ? tCommon("save") : tCommon("create")}
      >
        <TextInput label={t("name")} data-autofocus {...form.getInputProps("name")} />
        <TextInput
          label={`${t("contactName")} (${tCommon("optional")})`}
          {...form.getInputProps("contactName")}
        />
        <TextInput
          label={`${t("phone")} (${tCommon("optional")})`}
          inputMode="tel"
          {...form.getInputProps("phone")}
        />
        <TextInput
          label={`${t("email")} (${tCommon("optional")})`}
          type="email"
          {...form.getInputProps("email")}
        />
        {list.editing && (
          <Switch
            label={tCommon("active")}
            checked={form.values.isActive}
            onChange={(event) =>
              form.setFieldValue("isActive", event.currentTarget.checked)
            }
          />
        )}
      </FormModal>
    </>
  );
}
