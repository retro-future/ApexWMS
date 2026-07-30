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
import { useDebouncedValue, useDisclosure } from "@mantine/hooks";
import { IconPencil, IconPlus } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { ACTIONS_COLUMN_WIDTH, ListShell } from "@/components/ListShell";
import { useCan } from "@/components/MeProvider";
import { StatusBadge } from "@/components/StatusBadge";
import {
  useResourceCreate,
  useResourceList,
  useResourceUpdate,
} from "@/hooks/use-resource";
import { ApiError } from "@/lib/api";
import { errorMessage, notifySuccess } from "@/lib/notify";
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

  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [showInactive, setShowInactive] = useState(false);
  const [page, setPage] = useState(1);

  const [opened, modal] = useDisclosure(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const query = useResourceList<Supplier>("suppliers", {
    page,
    search: debouncedSearch || undefined,
    isActive: showInactive ? undefined : true,
  });

  const create = useResourceCreate<Supplier, Record<string, unknown>>("suppliers");
  const update = useResourceUpdate<Supplier, Record<string, unknown>>("suppliers");

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

  function open(supplier: Supplier | null) {
    setEditing(supplier);
    setFormError(null);
    form.setValues(
      supplier
        ? {
            name: supplier.name,
            contactName: supplier.contactName ?? "",
            phone: supplier.phone ?? "",
            email: supplier.email ?? "",
            isActive: supplier.isActive,
          }
        : EMPTY,
    );
    modal.open();
  }

  async function submit(values: Values) {
    setFormError(null);
    const payload = {
      name: values.name.trim(),
      contactName: values.contactName.trim() || null,
      phone: values.phone.trim() || null,
      email: values.email.trim() || null,
    };

    try {
      if (editing) {
        await update.mutateAsync({
          id: editing.id,
          payload: { ...payload, isActive: values.isActive },
        });
        notifySuccess(tCommon("updated"));
      } else {
        await create.mutateAsync(payload);
        notifySuccess(tCommon("created"));
      }
      modal.close();
    } catch (err) {
      if (err instanceof ApiError && err.isConflict) {
        form.setFieldError("name", err.message);
        return;
      }
      setFormError(errorMessage(err, tCommon("retry")));
    }
  }

  const suppliers = query.data?.items ?? [];

  return (
    <>
      <ListShell
        title={t("title")}
        subtitle={t("subtitle")}
        action={
          manage && (
            <Button leftSection={<IconPlus size={16} />} onClick={() => open(null)}>
              {t("new")}
            </Button>
          )
        }
        search={{
          value: search,
          onChange: (value) => {
            setSearch(value);
            setPage(1);
          },
          placeholder: t("searchPlaceholder"),
        }}
        showInactive={showInactive}
        onShowInactiveChange={(value) => {
          setShowInactive(value);
          setPage(1);
        }}
        isLoading={query.isLoading}
        error={query.error}
        isEmpty={suppliers.length === 0}
        total={query.data?.totalItems ?? 0}
        page={page}
        pagesCount={query.data?.pagesCount ?? 0}
        onPageChange={setPage}
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
        {suppliers.map((supplier) => (
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
                    onClick={() => open(supplier)}
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
        opened={opened}
        onClose={modal.close}
        title={editing ? t("editTitle") : t("newTitle")}
        onSubmit={form.onSubmit(submit)}
        busy={create.isPending || update.isPending}
        error={formError}
        submitLabel={editing ? tCommon("save") : tCommon("create")}
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
        {editing && (
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
