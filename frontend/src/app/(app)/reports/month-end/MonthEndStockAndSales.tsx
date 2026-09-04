"use client";

import { Anchor, Center, Stack, Table, Text, Title } from "@mantine/core";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { Subtotals } from "@/components/Subtotals";
import { TableScrollArea } from "@/components/TableScrollArea";
import {
  SALES_ROWS,
  STOCK_MOVE_LEDGER_TYPE,
  STOCK_MOVE_ROWS,
  amountIn,
  currenciesIn,
  ledgerHref,
  percentIn,
  stockMoveMinor,
} from "@/lib/month-end";
import type { Currency, CurrencySubtotal, MonthEndReport } from "@/lib/types";

/** Which sales rows drill into a ledger category. Margin is a sum, so none. */
const SALES_LEDGER_TYPE = {
  revenue: "sale_revenue",
  salesReturns: "sales_return_refund",
  costOfGoods: "cogs",
} as const;

/**
 * The close's two questions, each its own table.
 *
 * **Stock value** rolls opening inventory forward to closing. Every row is a
 * move on the shelf, shown in the *inventory* direction (`stockMoveMinor`),
 * so a supplier return reads as `-` — goods left — not `+` for the credit
 * coming back. That credit is the small block in between.
 *
 * **Sales** is the plain profit view and keeps §4.6's cash signs: revenue
 * positive, the cost against it negative, margin their sum.
 */
export function MonthEndStockAndSales({ report }: { report: MonthEndReport }) {
  const t = useTranslations("reports");
  const currencies = currenciesIn(report.figures);

  // No currency touched means no column to put a figure under, and a grid of
  // labels against nothing reads as broken rather than as a quiet month.
  if (currencies.length === 0) {
    return (
      <Center p="xl">
        <Text fw={500}>{t("noActivity")}</Text>
      </Center>
    );
  }

  const { figures } = report;

  return (
    <>
      <BlockHeading title={t("stockValueTitle")} hint={t("stockValueHint")} />
      <TableScrollArea>
        <Table highlightOnHover verticalSpacing="sm" miw={480}>
          <FigureHead currencies={currencies} />
          <Table.Tbody>
            <MoneyRow
              label={t("openingInventory")}
              currencies={currencies}
              amount={(currency) => amountIn(figures.openingInventory, currency)}
            />
            {STOCK_MOVE_ROWS.map((row) => (
              <MoneyRow
                key={row}
                label={t(row)}
                href={ledgerHref(STOCK_MOVE_LEDGER_TYPE[row], report.period)}
                currencies={currencies}
                amount={(currency) => stockMoveMinor(figures, row, currency)}
              />
            ))}
            <MoneyRow
              strong
              label={t("closingInventory")}
              currencies={currencies}
              amount={(currency) => amountIn(figures.closingInventory, currency)}
            />
          </Table.Tbody>
        </Table>
      </TableScrollArea>

      {figures.supplierReturnCredits.length > 0 && (
        <>
          <BlockHeading
            title={t("supplierRefundTitle")}
            hint={t("supplierRefundHint")}
          />
          <TableScrollArea>
            <Table verticalSpacing="sm" miw={360}>
              <Table.Tbody>
                <Table.Tr>
                  <Table.Td>
                    <Anchor
                      component={Link}
                      href={ledgerHref(
                        "supplier_return_credit",
                        report.period,
                      )}
                      size="sm"
                      fw={500}
                    >
                      {t("supplierRefundLabel")}
                    </Anchor>
                  </Table.Td>
                  <Table.Td ta="right">
                    <Subtotals subtotals={figures.supplierReturnCredits} />
                  </Table.Td>
                </Table.Tr>
              </Table.Tbody>
            </Table>
          </TableScrollArea>
        </>
      )}

      <BlockHeading title={t("salesTitle")} hint={t("costOfGoodsHint")} />
      <TableScrollArea>
        <Table highlightOnHover verticalSpacing="sm" miw={480}>
          <FigureHead currencies={currencies} />
          <Table.Tbody>
            {SALES_ROWS.map((row) => (
              <MoneyRow
                key={row}
                strong={row === "margin"}
                label={t(row)}
                href={
                  row in SALES_LEDGER_TYPE
                    ? ledgerHref(
                        SALES_LEDGER_TYPE[row as keyof typeof SALES_LEDGER_TYPE],
                        report.period,
                      )
                    : undefined
                }
                currencies={currencies}
                amount={(currency) =>
                  amountIn(figures[row] as CurrencySubtotal[], currency)
                }
              />
            ))}
            <Table.Tr>
              <Table.Td>
                <Text size="sm" fw={500}>
                  {t("marginPercent")}
                </Text>
              </Table.Td>
              {currencies.map((currency) => {
                const percent = percentIn(figures.marginPercent, currency);
                return (
                  <Table.Td key={currency}>
                    <Text
                      size="sm"
                      c={percent === null ? "dimmed" : undefined}
                    >
                      {percent === null ? "—" : `${percent}%`}
                    </Text>
                  </Table.Td>
                );
              })}
            </Table.Tr>
          </Table.Tbody>
        </Table>
      </TableScrollArea>
    </>
  );
}

function BlockHeading({ title, hint }: { title: string; hint: string }) {
  return (
    <Stack gap="3xs">
      <Title order={4}>{title}</Title>
      <Text size="sm" c="dimmed">
        {hint}
      </Text>
    </Stack>
  );
}

function FigureHead({ currencies }: { currencies: Currency[] }) {
  const t = useTranslations("reports");
  return (
    <Table.Thead>
      <Table.Tr>
        <Table.Th>{t("figure")}</Table.Th>
        {currencies.map((currency) => (
          <Table.Th key={currency}>{currency}</Table.Th>
        ))}
      </Table.Tr>
    </Table.Thead>
  );
}

/** One label against one amount per currency column, sign and all. */
function MoneyRow({
  label,
  href,
  currencies,
  amount,
  strong,
}: {
  label: string;
  href?: string;
  currencies: Currency[];
  amount: (currency: Currency) => number;
  strong?: boolean;
}) {
  return (
    <Table.Tr>
      <Table.Td>
        {href ? (
          <Anchor component={Link} href={href} size="sm" fw={strong ? 600 : 500}>
            {label}
          </Anchor>
        ) : (
          <Text size="sm" fw={strong ? 600 : 500}>
            {label}
          </Text>
        )}
      </Table.Td>
      {currencies.map((currency) => (
        <Table.Td key={currency}>
          <Subtotals
            subtotals={[{ currency, amountMinor: amount(currency) }]}
            fw={strong ? 600 : undefined}
          />
        </Table.Td>
      ))}
    </Table.Tr>
  );
}
