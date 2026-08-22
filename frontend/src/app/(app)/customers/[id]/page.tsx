"use client";

import {
  Alert,
  Anchor,
  Card,
  Center,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useParams } from "next/navigation";

import { DocumentStatusBadge } from "@/components/DocumentStatusBadge";
import { TableScrollArea } from "@/components/TableScrollArea";
import { useCustomerAccount } from "@/hooks/use-customer-account";
import { useDateFormat } from "@/hooks/use-date-format";
import { useCreditCompanyLookup } from "@/hooks/use-lookup";
import { formatMoney } from "@/lib/money";
import type { CreditInvoiceDebt } from "@/lib/types";

/**
 * FR-11.9: what this customer owes, and what they were sold on credit.
 *
 * Two tables, deliberately apart. Open debts are money the store is waiting
 * for; financed sales are money a credit company already paid in full, shown
 * only so the history is complete. Putting a zero-balance financed sale in
 * the same table as a real debt would invite the reader to add them up, and
 * PRD §4.7 calls attributing a company's debt to the customer the most
 * misleading thing this system could do.
 *
 * The balance is a single som number and nothing here stores it: it is
 * recomputed from `debt − Σ payments` on every request.
 */
export default function CustomerAccountPage() {
  const t = useTranslations("credit");
  const tCustomers = useTranslations("customers");
  const tCommon = useTranslations("common");
  const { formatDate } = useDateFormat();
  const { id } = useParams<{ id: string }>();

  const query = useCustomerAccount(id);
  const companies = useCreditCompanyLookup();

  if (query.isLoading) {
    return (
      <Center p="xl">
        <Loader size="sm" />
      </Center>
    );
  }

  const account = query.data;
  if (query.isError || !account) {
    return (
      <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
        {query.error instanceof Error ? query.error.message : tCustomers("notFound")}
      </Alert>
    );
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <Stack gap="2xs">
          <Title order={2}>{account.fullName}</Title>
          <Text size="sm" c="dimmed">
            {account.phone ?? tCommon("none")}
          </Text>
        </Stack>
        <Stack gap="3xs" align="flex-end">
          <Text size="xs" c="dimmed" tt="uppercase">
            {t("balance")}
          </Text>
          <Text size="xl" fw={700}>
            {formatMoney(account.balanceMinor, "UZS")}
          </Text>
        </Stack>
      </Group>

      <Card withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Stack gap="3xs">
            <Text fw={500}>{t("openDebts")}</Text>
            <Text size="sm" c="dimmed">
              {t("openDebtsHint")}
            </Text>
          </Stack>

          {account.openDebts.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t("noOpenDebts")}
            </Text>
          ) : (
            <TableScrollArea>
              <Table verticalSpacing="sm" miw={720}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t("invoice")}</Table.Th>
                    <Table.Th>{t("debt")}</Table.Th>
                    <Table.Th>{t("paid")}</Table.Th>
                    <Table.Th>{t("remaining")}</Table.Th>
                    <Table.Th>{t("age")}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {account.openDebts.map((debt) => (
                    <Table.Tr key={debt.invoiceId}>
                      <Table.Td>
                        <Group gap="2xs" wrap="nowrap">
                          <InvoiceLink debt={debt} />
                          <DocumentStatusBadge status={debt.status} />
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">
                          {formatMoney(debt.debtMinor ?? 0, "UZS")}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">{formatMoney(debt.paidMinor, "UZS")}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" fw={600}>
                          {formatMoney(debt.remainingMinor, "UZS")}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">
                          {debt.daysSinceSale === null
                            ? tCommon("none")
                            : t("days", { count: debt.daysSinceSale })}
                        </Text>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </TableScrollArea>
          )}
        </Stack>
      </Card>

      {account.financedSales.length > 0 && (
        <Card withBorder radius="md" padding="lg">
          <Stack gap="md">
            <Stack gap="3xs">
              <Text fw={500}>{t("financedSales")}</Text>
              <Text size="sm" c="dimmed">
                {t("financedSalesHint")}
              </Text>
            </Stack>

            <TableScrollArea>
              <Table verticalSpacing="sm" miw={640}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t("invoice")}</Table.Th>
                    <Table.Th>{t("company")}</Table.Th>
                    <Table.Th>{t("contractRef")}</Table.Th>
                    <Table.Th>{t("date")}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {account.financedSales.map((sale) => (
                    <Table.Tr key={sale.invoiceId}>
                      <Table.Td>
                        <Group gap="2xs" wrap="nowrap">
                          <InvoiceLink debt={sale} />
                          <DocumentStatusBadge status={sale.status} />
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">
                          {companies.get(sale.creditCompanyId) ?? tCommon("none")}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" c={sale.contractRef ? undefined : "dimmed"}>
                          {sale.contractRef ?? tCommon("none")}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">
                          {sale.confirmedAt ? formatDate(sale.confirmedAt) : tCommon("none")}
                        </Text>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </TableScrollArea>
          </Stack>
        </Card>
      )}
    </Stack>
  );
}

function InvoiceLink({ debt }: { debt: CreditInvoiceDebt }) {
  return (
    <Anchor component={Link} href={`/invoices/${debt.invoiceId}`} fw={500} size="sm">
      {debt.invoiceNumber}
    </Anchor>
  );
}
