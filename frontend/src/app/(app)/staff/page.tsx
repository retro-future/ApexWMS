"use client";

import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Center,
  CopyButton,
  Group,
  Loader,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useDisclosure } from "@mantine/hooks";
import {
  IconAlertCircle,
  IconCheck,
  IconCopy,
  IconInfoCircle,
  IconUserPlus,
  IconUserCog,
} from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormModal } from "@/components/FormModal";
import { ACTIONS_COLUMN_WIDTH } from "@/components/ListShell";
import { useCan, useMe } from "@/components/MeProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { TableScrollArea } from "@/components/TableScrollArea";
import { apiGet, apiSend } from "@/lib/api";
import { errorMessage, notifySuccess } from "@/lib/notify";
import { Permission } from "@/lib/permissions";
import { roleLabelKey } from "@/lib/roles";
import { TENANT_ROLES, type Employee, type InviteResult, type TenantRole } from "@/lib/types";

export default function StaffPage() {
  const t = useTranslations("staff");
  const tCommon = useTranslations("common");
  const tRoles = useTranslations("staff.roles");
  const me = useMe();
  const can = useCan();
  const manage = can(Permission.Users.Manage);
  const queryClient = useQueryClient();

  // Note: /users is NOT paged — it returns a plain list.
  const query = useQuery({
    queryKey: ["users"],
    queryFn: () => apiGet<Employee[]>("/users"),
  });

  const roleOptions = TENANT_ROLES.map((role) => ({
    value: role,
    label: tRoles(roleLabelKey(role)),
  }));

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <Stack gap="3xs">
          <Title order={2}>{t("title")}</Title>
          <Text size="sm" c="dimmed">
            {t("subtitle")}
          </Text>
        </Stack>
        {manage && <InviteButton roleOptions={roleOptions} />}
      </Group>

      {query.isError ? (
        <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
          {errorMessage(query.error, tCommon("retry"))}
        </Alert>
      ) : (
        <TableScrollArea>
          <Table highlightOnHover verticalSpacing="sm" miw={560}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t("name")}</Table.Th>
                <Table.Th>{t("role")}</Table.Th>
                <Table.Th>{tCommon("status")}</Table.Th>
                <Table.Th w={ACTIONS_COLUMN_WIDTH} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(query.data ?? []).map((employee) => (
                <Table.Tr key={employee.id}>
                  <Table.Td>
                    <Stack gap={0}>
                      <Group gap="xs">
                        <Text size="sm" fw={500}>
                          {employee.fullName}
                        </Text>
                        {employee.id === me.userId && (
                          <Badge size="xs" variant="light" color="gray">
                            you
                          </Badge>
                        )}
                      </Group>
                      <Text size="xs" c="dimmed">
                        {employee.email}
                      </Text>
                    </Stack>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="sm" variant="light">
                      {tRoles(roleLabelKey(employee.role))}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <StatusBadge isActive={employee.isActive} />
                  </Table.Td>
                  <Table.Td>
                    <Group justify="flex-end">
                      {manage && (
                        <ChangeRoleButton
                          employee={employee}
                          roleOptions={roleOptions}
                          onDone={() =>
                            queryClient.invalidateQueries({ queryKey: ["users"] })
                          }
                        />
                      )}
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>

          {query.isLoading && (
            <Center p="xl">
              <Loader size="sm" />
            </Center>
          )}
        </TableScrollArea>
      )}
    </Stack>
  );
}

type RoleOption = { value: TenantRole; label: string };

function InviteButton({ roleOptions }: { roleOptions: RoleOption[] }) {
  const t = useTranslations("staff");
  const tCommon = useTranslations("common");
  const [opened, modal] = useDisclosure(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [invite, setInvite] = useState<InviteResult | null>(null);

  const form = useForm<{ email: string; role: TenantRole }>({
    initialValues: { email: "", role: "tenant.seller" },
    validate: {
      email: (value) =>
        /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value.trim())
          ? null
          : tCommon("required"),
    },
  });

  const mutation = useMutation({
    mutationFn: (values: { email: string; role: TenantRole }) =>
      apiSend<InviteResult>("POST", "/users/invite", {
        email: values.email.trim(),
        role: values.role,
      }),
  });

  function open() {
    setInvite(null);
    setFormError(null);
    form.reset();
    modal.open();
  }

  async function submit(values: { email: string; role: TenantRole }) {
    setFormError(null);
    try {
      const result = await mutation.mutateAsync(values);
      if (result) setInvite(result);
    } catch (err) {
      setFormError(errorMessage(err, tCommon("retry")));
    }
  }

  return (
    <>
      <Button leftSection={<IconUserPlus size={16} />} onClick={open}>
        {t("invite")}
      </Button>

      {invite ? (
        <InviteResultModal
          opened={opened}
          onClose={modal.close}
          invite={invite}
        />
      ) : (
        <FormModal
          opened={opened}
          onClose={modal.close}
          title={t("inviteTitle")}
          onSubmit={form.onSubmit(submit)}
          busy={mutation.isPending}
          error={formError}
          submitLabel={t("invite")}
        >
          <TextInput
            label={t("email")}
            type="email"
            data-autofocus
            {...form.getInputProps("email")}
          />
          <Select
            label={t("role")}
            data={roleOptions}
            allowDeselect={false}
            {...form.getInputProps("role")}
          />
          <RoleHint role={form.values.role} />
        </FormModal>
      )}
    </>
  );
}

function RoleHint({ role }: { role: TenantRole }) {
  const t = useTranslations("staff.roleHints");
  return (
    <Text size="xs" c="dimmed">
      {t(roleLabelKey(role))}
    </Text>
  );
}

/**
 * The backend returns the raw invite token and sends no email — transactional
 * email does not exist in the project yet. So the link has to be handed over
 * by whoever created it.
 */
function InviteResultModal({
  opened,
  onClose,
  invite,
}: {
  opened: boolean;
  onClose: () => void;
  invite: InviteResult;
}) {
  const t = useTranslations("staff");
  const tCommon = useTranslations("common");

  const link =
    typeof window === "undefined"
      ? ""
      : `${window.location.origin}/accept-invite?token=${encodeURIComponent(invite.token)}`;

  return (
    <FormModal
      opened={opened}
      onClose={onClose}
      title={t("inviteCreated")}
      onSubmit={(event) => {
        event.preventDefault();
        onClose();
      }}
      submitLabel={tCommon("close")}
    >
      <Alert variant="light" color="blue" icon={<IconInfoCircle size={18} />}>
        {t("inviteLinkHint")}
      </Alert>
      <TextInput
        label={t("inviteLink")}
        value={link}
        readOnly
        onFocus={(event) => event.currentTarget.select()}
        rightSection={
          <CopyButton value={link}>
            {({ copied, copy }) => (
              <ActionIcon
                variant="subtle"
                color={copied ? "teal" : "gray"}
                onClick={copy}
                aria-label={tCommon("copy")}
              >
                {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
              </ActionIcon>
            )}
          </CopyButton>
        }
      />
    </FormModal>
  );
}

function ChangeRoleButton({
  employee,
  roleOptions,
  onDone,
}: {
  employee: Employee;
  roleOptions: RoleOption[];
  onDone: () => void;
}) {
  const t = useTranslations("staff");
  const tCommon = useTranslations("common");
  const [opened, modal] = useDisclosure(false);
  const [role, setRole] = useState<TenantRole>(employee.role);
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (next: TenantRole) =>
      apiSend<null>("PATCH", `/users/${employee.id}/role`, { role: next }),
  });

  function open() {
    setRole(employee.role);
    setFormError(null);
    modal.open();
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    try {
      await mutation.mutateAsync(role);
      notifySuccess(t("roleChanged"));
      onDone();
      modal.close();
    } catch (err) {
      // 409 LastOwnerError lands here: a store must keep one Owner.
      setFormError(errorMessage(err, tCommon("retry")));
    }
  }

  return (
    <>
      <ActionIcon
        variant="subtle"
        aria-label={t("changeRole")}
        onClick={open}
      >
        <IconUserCog size={16} />
      </ActionIcon>

      <FormModal
        opened={opened}
        onClose={modal.close}
        title={t("changeRoleTitle", { name: employee.fullName })}
        onSubmit={submit}
        busy={mutation.isPending}
        error={formError}
        submitLabel={tCommon("save")}
      >
        <Select
          label={t("role")}
          data={roleOptions}
          value={role}
          onChange={(value) => value && setRole(value as TenantRole)}
          allowDeselect={false}
        />
        <RoleHint role={role} />
      </FormModal>
    </>
  );
}
