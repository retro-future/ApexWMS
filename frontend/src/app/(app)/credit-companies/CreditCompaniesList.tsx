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

  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [showInactive, setShowInactive] = useState(false);
  const [page, setPage] = useState(1);

  const [opened, modal] = useDisclosure(false);
  const [editing, setEditing] = useState<CreditCompany | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const query = useResourceList<CreditCompany>("credit-companies", {
    page,
    search: debouncedSearch || undefined,
    isActive: showInactive ? undefined : true,
  });

  const create = useResourceCreate<CreditCompany, Record<string, unknown>>(
    "credit-companies",
  );
  const update = useResourceUpdate<CreditCompany, Record<string, unknown>>(
    "credit-companies",
  );

  const form = useForm<Values>({
    initialValues: EMPTY,
    validate: {
      name: (value) => (value.trim() ? null : tCommon("required")),
    },
  });

  function open(company: CreditCompany | null) {
    setEditing(company);
    setFormError(null);
    form.setValues(
      company
        ? {
            name: company.name,
            contactName: company.contactName ?? "",
            phone: company.phone ?? "",
            isActive: company.isActive,
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

  const companies = query.data?.items ?? [];

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
        isEmpty={companies.length === 0}
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
        {companies.map((company) => (
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
                    onClick={() => open(company)}
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
        {editing && (
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
