"use client";

import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type { CustomerAccount } from "@/lib/types";

/**
 * FR-11.9's account, which is a sub-resource rather than a row.
 *
 * Not `useResourceItem`: that builds `/{resource}/{id}` and keys the cache on
 * the id alone, and smuggling `"{id}/account"` through it would make the key
 * lie about what it holds. The account is also gated on its own permission
 * (`CustomerAccount.View`), separately from reading the customer.
 */
export function useCustomerAccount(customerId: string, enabled = true) {
  return useQuery<CustomerAccount>({
    queryKey: ["customers", "account", customerId],
    queryFn: () => apiGet<CustomerAccount>(`/customers/${customerId}/account`),
    enabled,
  });
}
