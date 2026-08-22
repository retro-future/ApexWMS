"use client";

import { ActionIcon, Button, Group, Switch, Table, Text, TextInput } from "@mantine/core";
import { useForm } from "@mantine/form";
import { IconPencil, IconPlus } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { FormModal } from "@/components/FormModal";
import { ACTIONS_COLUMN_WIDTH, ListShell } from "@/components/ListShell";
import { useCan } from "@/components/MeProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { useCrudEntityList } from "@/hooks/use-crud-entity-list";
import { Permission } from "@/lib/permissions";
import type { Location } from "@/lib/types";

type Values = { name: string; isActive: boolean };

const EMPTY: Values = { name: "", isActive: true };

export default function LocationsPage() {
  const t = useTranslations("locations");
  const tCommon = useTranslations("common");
  const can = useCan();
  const manage = can(Permission.Location.Manage);

  const form = useForm<Values>({
    initialValues: EMPTY,
    validate: { name: (value) => (value.trim() ? null : tCommon("required")) },
  });

  const list = useCrudEntityList<Location, Values>("locations", form, {
    empty: EMPTY,
    toValues: (location) => ({ name: location.name, isActive: location.isActive }),
    toPayload: (values) => ({ name: values.name.trim() }),
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
            <Table.Th>{tCommon("status")}</Table.Th>
            <Table.Th w={ACTIONS_COLUMN_WIDTH} />
          </Table.Tr>
        }
      >
        {list.items.map((location) => (
          <Table.Tr key={location.id}>
            <Table.Td>
              <Text size="sm" fw={500}>
                {location.name}
              </Text>
            </Table.Td>
            <Table.Td>
              <StatusBadge isActive={location.isActive} />
            </Table.Td>
            <Table.Td>
              <Group justify="flex-end">
                {manage && (
                  <ActionIcon
                    variant="subtle"
                    aria-label={tCommon("edit")}
                    onClick={() => list.open(location)}
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
