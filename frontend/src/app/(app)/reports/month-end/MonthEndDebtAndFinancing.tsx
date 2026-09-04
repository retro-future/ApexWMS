"use client";

import { Anchor, Center, Stack, Table, Text, Title } from "@mantine/core";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { Subtotals } from "@/components/Subtotals";
import { TableScrollArea } from "@/components/TableScrollArea";
import { invoicesHref, ledgerHref } from "@/lib/month-end";
import { formatMoney } from "@/lib/money";
import type {
  DebtMovement,
  MonthEndReport,
  PaymentType,
  Period,
} from "@/lib/types";

/**
 * The close's other half: what customers owe and how the store actually sells
 * (FR-10.5). Split off the main screen because four tables in one component is
 * past what a page should hold, not because these two belong together — they
 * are simply the two blocks that are not the accrual view.
 */
export function MonthEndDebtAndFinancing({
  report,
}: {
  report: MonthEndReport;
}) {
  const t = useTranslations("reports");

  return (
    <>
      <Stack gap="3xs">
        <Title order={4}>{t("debtMovement")}</Title>
        <Text size="sm" c="dimmed">
          {t("debtMovementHint")}
        </Text>
      </Stack>

      <TableScrollArea>
        <Table verticalSpacing="sm" miw={360}>
          <Table.Tbody>
            {DEBT_LINES.map(({ key, field, strong }) => {
              const href = debtLineHref(field, report.period);
              return (
                <Table.Tr key={key}>
                  <Table.Td>
                    {href ? (
                      <Anchor
                        component={Link}
                        href={href}
                        size="sm"
                        fw={strong ? 600 : 500}
                      >
                        {t(key)}
                      </Anchor>
                    ) : (
                      <Text size="sm" fw={strong ? 600 : 500}>
                        {t(key)}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td ta="right">
                    <Text size="sm" fw={strong ? 600 : undefined}>
                      {formatMoney(report.debt[field], report.debt.currency)}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </TableScrollArea>

      <Title order={4}>{t("salesByFinancing")}</Title>

      <TableScrollArea>
        <Table highlightOnHover verticalSpacing="sm" miw={480}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t("financingType")}</Table.Th>
              <Table.Th>{t("invoiceCount")}</Table.Th>
              <Table.Th>{t("revenue")}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {report.financing.map((row) => (
              <Table.Tr
                key={`${row.paymentType}-${row.creditCompanyId ?? ""}-${row.revenue[0]?.currency ?? ""}`}
              >
                <Table.Td>
                  <FinancingLabel
                    paymentType={row.paymentType}
                    company={row.creditCompanyName}
                  />
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{row.invoiceCount}</Text>
                </Table.Td>
                <Table.Td>
                  <Subtotals subtotals={row.revenue} />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>

        {report.financing.length === 0 && (
          <Center p="xl">
            <Text fw={500}>{t("noSales")}</Text>
          </Center>
        )}
      </TableScrollArea>
    </>
  );
}

/** In movement order, closing last — the line the other four have to reach. */
const DEBT_LINES: readonly {
  key: string;
  field: keyof Omit<DebtMovement, "currency">;
  strong: boolean;
}[] = [
  { key: "debtOpening", field: "openingMinor", strong: false },
  { key: "debtBooked", field: "bookedMinor", strong: false },
  { key: "debtCollected", field: "collectedMinor", strong: false },
  { key: "debtVoided", field: "voidedMinor", strong: false },
  { key: "debtRelieved", field: "relievedMinor", strong: false },
  { key: "debtClosing", field: "closingMinor", strong: true },
];

/**
 * The three movement lines drill into the documents behind them; opening and
 * closing are balances rolled from the ledger, not a list.
 */
function debtLineHref(
  field: keyof Omit<DebtMovement, "currency">,
  period: Period,
): string | undefined {
  switch (field) {
    case "bookedMinor":
      return invoicesHref({
        paymentType: "store_credit",
        status: "confirmed",
        period,
      });
    case "collectedMinor":
      return ledgerHref("payment_received", period);
    case "voidedMinor":
      return invoicesHref({
        paymentType: "store_credit",
        status: "cancelled",
        period,
      });
    default:
      return undefined;
  }
}

const PAYMENT_TYPE_LABELS: Record<PaymentType, string> = {
  paid_in_full: "paidInFull",
  credit_company: "creditCompany",
  store_credit: "storeCredit",
};

/** A financed sale is only interesting named by its company. */
function FinancingLabel({
  paymentType,
  company,
}: {
  paymentType: PaymentType;
  company: string | null;
}) {
  const tCredit = useTranslations("credit");
  const label = tCredit(PAYMENT_TYPE_LABELS[paymentType]);

  return (
    <Stack gap={0}>
      <Text size="sm" fw={500}>
        {company ?? label}
      </Text>
      {company && (
        <Text size="xs" c="dimmed">
          {label}
        </Text>
      )}
    </Stack>
  );
}
