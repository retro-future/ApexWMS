"use client";

import { useQueries } from "@tanstack/react-query";
import { useMemo } from "react";

import { useResourceList } from "@/hooks/use-resource";
import { apiGet } from "@/lib/api";
import { isEditable } from "@/lib/documents";
import { chargedMinor, isSerial, type QuoteMap } from "@/lib/invoices";
import type { DeviceUnit, Product, SalesInvoice } from "@/lib/types";

/**
 * What a draft invoice would charge right now.
 *
 * A draft's own payload carries no prices (FR-4.5b1), so the figure comes
 * from the two places the server already publishes one: a handset's
 * `resolvedPrice`, which is FR-2.14 applied to that unit, and a product's
 * `defaultSalePrice` for an accessory line. Neither is re-derived here —
 * this assembles what the server said, it does not re-implement the rule.
 *
 * Both requests are keyed exactly as the hooks that already make them:
 * `["device-units", "item", id]` is `useResourceItem`'s key, so a handset
 * already opened costs nothing, and the product page size matches
 * `useProductLookup`'s so the two share one cache entry.
 *
 * A Seller can do all of this — reading a unit needs only `Catalog.View`.
 */

/** Matches `useProductLookup`'s params, so it is the same cached request. */
const PAGE_SIZE = 200;

export function useInvoiceQuote(invoice: SalesInvoice | undefined): {
  quotes: QuoteMap;
  isLoading: boolean;
} {
  const lines = invoice?.lines ?? [];
  // A confirmed invoice carries its own snapshot; quoting it again would
  // spend a request per handset to answer a question already answered.
  const wanted = invoice !== undefined && isEditable(invoice.status);

  const unitIds = wanted ? [
    ...new Set(
      lines.filter(isSerial).flatMap((line) => (line.deviceUnitId ? [line.deviceUnitId] : [])),
    ),
  ] : [];

  const units = useQueries({
    queries: unitIds.map((id) => ({
      queryKey: ["device-units", "item", id],
      queryFn: () => apiGet<DeviceUnit>(`/device-units/${id}`),
    })),
  });

  const products = useResourceList<Product>(
    "products",
    { page: 1, pageSize: PAGE_SIZE },
    { enabled: wanted },
  );

  const unitsLoading = units.some((query) => query.isLoading);
  // A stable dependency for the memo: the ids and prices that came back,
  // not the query objects, which are new on every render.
  const unitPrices = units
    .map((query) => `${query.data?.id}:${query.data?.resolvedPriceMinor}`)
    .join("|");

  const quotes = useMemo(() => {
    const unitById = new Map<string, DeviceUnit>();
    for (const query of units) {
      if (query.data) unitById.set(query.data.id, query.data);
    }
    const productById = new Map<string, Product>();
    for (const product of products.data?.items ?? []) productById.set(product.id, product);

    const map: QuoteMap = new Map();
    for (const line of lines) {
      // `resolvedPrice: null` means FR-2.14 refuses — the handset needs
      // pricing. Not zero, and never the catalog price of a used phone.
      const resolvedMinor = line.deviceUnitId
        ? (unitById.get(line.deviceUnitId)?.resolvedPriceMinor ?? null)
        : (productById.get(line.productId)?.defaultSalePriceMinor ?? null);

      map.set(line.id, {
        resolvedMinor,
        chargedMinor: chargedMinor(line, resolvedMinor),
        currency: line.currency,
        isOverride: line.overridePriceMinor !== null,
      });
    }
    return map;
    // `lines` and `units` are fresh on every render; what changes the
    // answer is the invoice and the prices that came back for it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoice, products.data, unitPrices]);

  return { quotes, isLoading: unitsLoading || products.isLoading };
}
