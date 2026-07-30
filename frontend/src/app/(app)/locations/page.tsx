"use client";

import {
  ActionIcon,
  Button,
  Group,
  Switch,
  Table,
  Text,
  TextInput,
} from "@mantine/core";
import { useDebouncedValue, useDisclosure } from "@mantine/hooks";
import { IconPencil, IconPlus } from "@tabler/icons-react";
import { useForm } from "@mantine/form";
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
import type { Location } from "@/lib/types";

type Values = { name: string; isActive: boolean };

export default function LocationsPage() {
  const t = useTranslations("locations");
  const tCommon = useTranslations("common");
  const can = useCan();
  const manage = can(Permission.Location.Manage);

  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [showInactive, setShowInactive] = useState(false);
  const [page, setPage] = useState(1);

  const [opened, modal] = useDisclosure(false);
  const [editing, setEditing] = useState<Location | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const query = useResourceList<Location>("locations", {
    page,
    search: debouncedSearch || undefined,
    isActive: showInactive ? undefined : true,
  });

  const create = useResourceCreate<Location, Record<string, unknown>>("locations");
  const update = useResourceUpdate<Location, Record<string, unknown>>("locations");

  const form = useForm<Values>({
    initialValues: { name: "", isActive: true },
    validate: { name: (value) => (value.trim() ? null : tCommon("required")) },
  });

  function open(location: Location | null) {
    setEditing(location);
    setFormError(null);
    form.setValues({
      name: location?.name ?? "",
      isActive: location?.isActive ?? true,
    });
    modal.open();
  }

  async function submit(values: Values) {
    setFormError(null);
    try {
      if (editing) {
        await update.mutateAsync({
          id: editing.id,
          payload: { name: values.name.trim(), isActive: values.isActive },
        });
        notifySuccess(tCommon("updated"));
      } else {
        await create.mutateAsync({ name: values.name.trim() });
        notifySuccess(tCommon("created"));
      }
      modal.close();
    } catch (err) {
      // Names are unique per store — a 409 belongs on the field.
      if (err instanceof ApiError && err.isConflict) {
        form.setFieldError("name", err.message);
        return;
      }
      setFormError(errorMessage(err, tCommon("retry")));
    }
  }

  const locations = query.data?.items ?? [];

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
        isEmpty={locations.length === 0}
        total={query.data?.totalItems ?? 0}
        page={page}
        pagesCount={query.data?.pagesCount ?? 0}
        onPageChange={setPage}
        head={
          <Table.Tr>
            <Table.Th>{t("name")}</Table.Th>
            <Table.Th>{tCommon("status")}</Table.Th>
            <Table.Th w={ACTIONS_COLUMN_WIDTH} />
          </Table.Tr>
        }
      >
        {locations.map((location) => (
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
                    onClick={() => open(location)}
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
