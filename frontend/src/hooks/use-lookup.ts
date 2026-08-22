"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { useCan } from "@/components/MeProvider";
import { useResourceList } from "@/hooks/use-resource";
import { apiGet } from "@/lib/api";
import { Permission } from "@/lib/permissions";
import type {
  CreditCompany,
  Customer,
  Employee,
  Location,
  Product,
  Supplier,
} from "@/lib/types";

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

export type LookupMap<T = unknown> = {
  /** The display name for an id, or `undefined` when it is not loaded/permitted. */
  get: (id: string | null | undefined) => string | undefined;
  /**
   * The rows themselves, for the screens that offer them as a filter rather
   * than only resolving ids. Empty where the permission is not held.
   */
  all: T[];
  isLoading: boolean;
  error: unknown;
};

function useLookup<T extends { id: string }>(
  resource: string,
  label: (item: T) => string,
  allowed: boolean,
): LookupMap<T> {
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
    all: query.data?.items ?? [],
    isLoading: query.isLoading,
    error: query.error,
  };
}

export function useProductLookup(): LookupMap<Product> {
  const can = useCan();
  return useLookup<Product>(
    "products",
    (product) => `${product.name} (${product.sku})`,
    can(Permission.Catalog.View),
  );
}

export function useSupplierLookup(): LookupMap<Supplier> {
  const can = useCan();
  return useLookup<Supplier>(
    "suppliers",
    (supplier) => supplier.name,
    can(Permission.Catalog.View),
  );
}

export function useLocationLookup(): LookupMap<Location> {
  const can = useCan();
  return useLookup<Location>(
    "locations",
    (location) => location.name,
    can(Permission.Location.View),
  );
}

export function useCustomerLookup(): LookupMap<Customer> {
  const can = useCan();
  return useLookup<Customer>(
    "customers",
    (customer) => customer.fullName,
    can(Permission.Customer.View),
  );
}

export function useCreditCompanyLookup(): LookupMap<CreditCompany> {
  const can = useCan();
  return useLookup<CreditCompany>(
    "credit-companies",
    (company) => company.name,
    can(Permission.CreditCompany.View),
  );
}

/**
 * Who did a thing — an invoice's author, its confirmer, and the manager who
 * approved a line's price (FR-4.5f).
 *
 * It cannot go through `useLookup`: `/users` is not paged, it returns a
 * plain list. And it is gated on `Users.View`, which only an Owner holds —
 * so a Seller reading an invoice they overrode sees a dash where the name
 * would be, rather than a 403 on the whole page.
 */
export function useEmployeeLookup(): LookupMap<Employee> {
  const can = useCan();
  const allowed = can(Permission.Users.View);

  const query = useQuery({
    queryKey: ["users"],
    queryFn: () => apiGet<Employee[]>("/users"),
    enabled: allowed,
  });

  const byId = useMemo(() => {
    const map = new Map<string, string>();
    for (const employee of query.data ?? []) map.set(employee.id, employee.fullName);
    return map;
  }, [query.data]);

  return {
    get: (id) => (id ? byId.get(id) : undefined),
    all: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error,
  };
}
