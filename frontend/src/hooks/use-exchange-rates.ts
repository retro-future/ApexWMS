"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiSend } from "@/lib/api";
import type { CurrentRates, ExchangeRate, RateKind } from "@/lib/types";

const KEY = ["rates"];

/** Both rates in force, under one key for every screen that shows them. */
export function useCurrentRates() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => apiGet<CurrentRates>("/exchange-rates/current"),
  });
}

/**
 * Whether the rate on screen is yesterday's or older.
 *
 * False while the query is in flight, so a slow read does not flash a
 * warning that then disappears. Also false for a store that has never
 * quoted one: nothing has gone stale, nothing has been set.
 */
export function useRateIsStale(): boolean {
  const { data } = useCurrentRates();
  return Boolean(data?.sale?.isStale || data?.buyback?.isStale);
}

export function useSetRate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (values: { kind: RateKind; somPerUsd: string }) =>
      apiSend<ExchangeRate>("POST", "/exchange-rates", values),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}
