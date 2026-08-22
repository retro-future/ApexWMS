"use client";

import { ActionIcon, Anchor, Button, Group, Switch, Table, Text, TextInput } from "@mantine/core";
import { useForm } from "@mantine/form";
import { IconPencil, IconPlus } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { FormModal } from "@/components/FormModal";
import { ACTIONS_COLUMN_WIDTH, ListShell } from "@/components/ListShell";
import { useCan } from "@/components/MeProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { useCrudEntityList } from "@/hooks/use-crud-entity-list";
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
  const account = can(Permission.CustomerAccount.View);

  const form = useForm<Values>({
    initialValues: EMPTY,
    validate: {
      fullName: (value) => (value.trim() ? null : tCommon("required")),
    },
  });

  const list = useCrudEntityList<Customer, Values>("customers", form, {
    empty: EMPTY,
    toValues: (customer) => ({
      fullName: customer.fullName,
      phone: customer.phone ?? "",
      isActive: customer.isActive,
    }),
    toPayload: (values) => ({
      fullName: values.fullName.trim(),
      phone: values.phone.trim() || null,
    }),
    conflictField: "fullName",
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
            <Table.Th>{t("fullName")}</Table.Th>
            <Table.Th>{t("phone")}</Table.Th>
            <Table.Th>{tCommon("status")}</Table.Th>
            <Table.Th w={ACTIONS_COLUMN_WIDTH} />
          </Table.Tr>
        }
      >
        {list.items.map((customer) => (
          <Table.Tr key={customer.id}>
            <Table.Td>
              {/* The account is where their debt lives (§4.7) — nothing on
                  this row can show it, because a balance spans invoices. */}
              {account ? (
                <Anchor
                  component={Link}
                  href={`/customers/${customer.id}`}
                  size="sm"
                  fw={500}
                >
                  {customer.fullName}
                </Anchor>
              ) : (
                <Text size="sm" fw={500}>
                  {customer.fullName}
                </Text>
              )}
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
                    onClick={() => list.open(customer)}
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
