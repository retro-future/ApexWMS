"use client";

import { useMemo } from "react";

import { useCan } from "@/components/MeProvider";
import { useResourceList } from "@/hooks/use-resource";
import { Permission } from "@/lib/permissions";
import type { Customer, Location, Product, Supplier } from "@/lib/types";

/**
 * Documents reference their products, suppliers, locations and customers by
 * id — the payloads carry no names — so every inbound screen needs the same
 * id → name map. One cached list request per resource serves the whole page,
 * which is why this is a hook rather than a per-row fetch.
 *
 * Each map is gated on the permission its endpoint requires. A Storekeeper
 * holds Catalog.View and Location.View but *not* Customer.View, so a
 * trade-in receipt's customer must degrade to a dash rather than 403 the
 * page it appears on.
 */

/** One request, not one per page: reference lists are small and the API caps page size at 200. */
const PAGE_SIZE = 200;

export type LookupMap = {
  /** The display name for an id, or `undefined` when it is not loaded/permitted. */
  get: (id: string | null | undefined) => string | undefined;
  isLoading: boolean;
};

function useLookup<T extends { id: string }>(
  resource: string,
  label: (item: T) => string,
  allowed: boolean,
): LookupMap {
  // No `isActive` filter: deactivated rows still appear on documents raised
  // before they were retired, and a receipt from March must not lose its
  // supplier's name.
  const query = useResourceList<T>(
    resource,
    { page: 1, pageSize: PAGE_SIZE },
    { enabled: allowed },
  );

  const byId = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of query.data?.items ?? []) map.set(item.id, label(item));
    return map;
    // `label` is a fresh closure on every render; the data is what matters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data]);

  return {
    get: (id) => (id ? byId.get(id) : undefined),
    isLoading: query.isLoading,
  };
}

export function useProductLookup(): LookupMap {
  const can = useCan();
  return useLookup<Product>(
    "products",
    (product) => `${product.name} (${product.sku})`,
    can(Permission.Catalog.View),
  );
}

export function useSupplierLookup(): LookupMap {
  const can = useCan();
  return useLookup<Supplier>(
    "suppliers",
    (supplier) => supplier.name,
    can(Permission.Catalog.View),
  );
}

export function useLocationLookup(): LookupMap {
  const can = useCan();
  return useLookup<Location>(
    "locations",
    (location) => location.name,
    can(Permission.Location.View),
  );
}

export function useCustomerLookup(): LookupMap {
  const can = useCan();
  return useLookup<Customer>(
    "customers",
    (customer) => customer.fullName,
    can(Permission.Customer.View),
  );
}
