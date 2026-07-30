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

export type ListParams = {
  page: number;
  pageSize?: number;
  search?: string;
  isActive?: boolean;
  trackingType?: string;
};

export function useResourceList<T>(resource: string, params: ListParams) {
  return useQuery<Paged<T>>({
    queryKey: [resource, params],
    queryFn: () => apiGetPaged<T>(`/${resource}${queryString(params)}`),
    // Keeps the previous page on screen while the next one loads, instead of
    // collapsing the table to a spinner on every keystroke.
    placeholderData: keepPreviousData,
  });
}

export function useResourceItem<T>(resource: string, id: string) {
  return useQuery<T>({
    queryKey: [resource, "item", id],
    queryFn: () => apiGet<T>(`/${resource}/${id}`),
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
