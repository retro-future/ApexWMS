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
import type { CreditCompany } from "@/lib/types";

type Values = {
  name: string;
  contactName: string;
  phone: string;
  isActive: boolean;
};

const EMPTY: Values = { name: "", contactName: "", phone: "", isActive: true };

/**
 * No money columns, and there will not be any. The company pays the store in
 * full at sale time (PRD §4.7), so nothing is ever owed to or by it — this
 * list is a set of labels that financed sales point at.
 *
 * Only an Owner maintains it, but a Seller reads it: picking the company is
 * part of closing a financed sale at the counter (§2.1).
 */
export function CreditCompaniesList() {
  const t = useTranslations("creditCompanies");
  const tCommon = useTranslations("common");
  const can = useCan();
  const manage = can(Permission.CreditCompany.Manage);

  const form = useForm<Values>({
    initialValues: EMPTY,
    validate: {
      name: (value) => (value.trim() ? null : tCommon("required")),
    },
  });

  const list = useCrudEntityList<CreditCompany, Values>("credit-companies", form, {
    empty: EMPTY,
    toValues: (company) => ({
      name: company.name,
      contactName: company.contactName ?? "",
      phone: company.phone ?? "",
      isActive: company.isActive,
    }),
    toPayload: (values) => ({
      name: values.name.trim(),
      contactName: values.contactName.trim() || null,
      phone: values.phone.trim() || null,
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
        {list.items.map((company) => (
          <Table.Tr key={company.id}>
            <Table.Td>
              <Text size="sm" fw={500}>
                {company.name}
              </Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm" c={company.contactName ? undefined : "dimmed"}>
                {company.contactName ?? tCommon("none")}
              </Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm" c={company.phone ? undefined : "dimmed"}>
                {company.phone ?? tCommon("none")}
              </Text>
            </Table.Td>
            <Table.Td>
              <StatusBadge isActive={company.isActive} />
            </Table.Td>
            <Table.Td>
              <Group justify="flex-end">
                {manage && (
                  <ActionIcon
                    variant="subtle"
                    aria-label={tCommon("edit")}
                    onClick={() => list.open(company)}
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
        {list.editing && (
          <Switch
            label={tCommon("active")}
            description={t("deactivateHint")}
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
