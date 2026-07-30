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
import type { Customer } from "@/lib/types";

type Values = { fullName: string; phone: string; isActive: boolean };

const EMPTY: Values = { fullName: "", phone: "", isActive: true };

/**
 * Two fields, on purpose. PRD §1.3: "Customer exists as a name + phone number
 * on an invoice. Nothing more." Balances and history are derived from the
 * ledger at M5b — there is nothing to store here.
 */
export default function CustomersPage() {
  const t = useTranslations("customers");
  const tCommon = useTranslations("common");
  const can = useCan();
  const manage = can(Permission.Customer.Manage);

  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [showInactive, setShowInactive] = useState(false);
  const [page, setPage] = useState(1);

  const [opened, modal] = useDisclosure(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const query = useResourceList<Customer>("customers", {
    page,
    search: debouncedSearch || undefined,
    isActive: showInactive ? undefined : true,
  });

  const create = useResourceCreate<Customer, Record<string, unknown>>("customers");
  const update = useResourceUpdate<Customer, Record<string, unknown>>("customers");

  const form = useForm<Values>({
    initialValues: EMPTY,
    validate: {
      fullName: (value) => (value.trim() ? null : tCommon("required")),
    },
  });

  function open(customer: Customer | null) {
    setEditing(customer);
    setFormError(null);
    form.setValues(
      customer
        ? {
            fullName: customer.fullName,
            phone: customer.phone ?? "",
            isActive: customer.isActive,
          }
        : EMPTY,
    );
    modal.open();
  }

  async function submit(values: Values) {
    setFormError(null);
    const payload = {
      fullName: values.fullName.trim(),
      phone: values.phone.trim() || null,
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
        form.setFieldError("fullName", err.message);
        return;
      }
      setFormError(errorMessage(err, tCommon("retry")));
    }
  }

  const customers = query.data?.items ?? [];

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
        isEmpty={customers.length === 0}
        total={query.data?.totalItems ?? 0}
        page={page}
        pagesCount={query.data?.pagesCount ?? 0}
        onPageChange={setPage}
        head={
          <Table.Tr>
            <Table.Th>{t("fullName")}</Table.Th>
            <Table.Th>{t("phone")}</Table.Th>
            <Table.Th>{tCommon("status")}</Table.Th>
            <Table.Th w={ACTIONS_COLUMN_WIDTH} />
          </Table.Tr>
        }
      >
        {customers.map((customer) => (
          <Table.Tr key={customer.id}>
            <Table.Td>
              <Text size="sm" fw={500}>
                {customer.fullName}
              </Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm" c={customer.phone ? undefined : "dimmed"}>
                {customer.phone ?? tCommon("none")}
              </Text>
            </Table.Td>
            <Table.Td>
              <StatusBadge isActive={customer.isActive} />
            </Table.Td>
            <Table.Td>
              <Group justify="flex-end">
                {manage && (
                  <ActionIcon
                    variant="subtle"
                    aria-label={tCommon("edit")}
                    onClick={() => open(customer)}
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
        <TextInput
          label={t("fullName")}
          data-autofocus
          {...form.getInputProps("fullName")}
        />
        <TextInput
          label={`${t("phone")} (${tCommon("optional")})`}
          inputMode="tel"
          {...form.getInputProps("phone")}
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
