"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiGet, apiGetPaged, apiSend, queryString, type Paged } from "@/lib/api";

/**
 * The four catalog resources are the same CRUD shape over the same enveloped
 * API, so the fetching lives here once. Columns and form fields stay explicit
 * on each page — this abstracts the plumbing, not the screens.
 *
 * `resource` is the path segment: "products", "locations", …
 */

/**
 * Filters are open-ended on purpose: each list endpoint takes its own
 * (`trackingType` on products, `acquisitionSource` on receipts, ...) and
 * `queryString` already drops the empty ones.
 */
export type ListParams = {
  page: number;
  pageSize?: number;
  search?: string;
  isActive?: boolean;
} & Record<string, string | number | boolean | undefined | null>;

/**
 * `enabled` is an option rather than a param: a disabled query must not
 * put anything in the URL. It is how a page skips a request the signed-in
 * role has no permission for instead of rendering a 403.
 */
type QueryOptions = { enabled?: boolean };

export function useResourceList<T>(
  resource: string,
  params: ListParams,
  options: QueryOptions = {},
) {
  return useQuery<Paged<T>>({
    queryKey: [resource, params],
    queryFn: () => apiGetPaged<T>(`/${resource}${queryString(params)}`),
    // Keeps the previous page on screen while the next one loads, instead of
    // collapsing the table to a spinner on every keystroke.
    placeholderData: keepPreviousData,
    enabled: options.enabled ?? true,
  });
}

export function useResourceItem<T>(
  resource: string,
  id: string,
  options: QueryOptions = {},
) {
  return useQuery<T>({
    queryKey: [resource, "item", id],
    queryFn: () => apiGet<T>(`/${resource}/${id}`),
    enabled: options.enabled ?? true,
  });
}

export function useResourceCreate<T, TPayload>(resource: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TPayload) =>
      apiSend<T>("POST", `/${resource}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [resource] }),
  });
}

export function useResourceUpdate<T, TPayload>(resource: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TPayload }) =>
      apiSend<T>("PATCH", `/${resource}/${id}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [resource] }),
  });
}

/** Wraps a filter setter so changing it also resets pagination to page 1. */
export function makePageReset(setPage: (page: number) => void) {
  return function reset<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value);
      setPage(1);
    };
  };
}
