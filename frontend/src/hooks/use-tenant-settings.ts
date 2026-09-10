"use client";

import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type { TenantSettings } from "@/lib/types";

/**
 * The store's own settings, cached under one key for every screen that
 * needs them. The settings page owns the writes and invalidates this.
 */
export function useTenantSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: () => apiGet<TenantSettings>("/settings/tenant"),
  });
}

/**
 * Whether to offer the money that physically changed hands (§4.5b).
 *
 * Defaults to `false` while the query is in flight, so a slow settings read
 * shows the smaller screen rather than a field that flickers away. The
 * server refuses the write either way — this only decides what is offered.
 */
export function useRunsTill(): boolean {
  return useTenantSettings().data?.runsTill ?? false;
}
