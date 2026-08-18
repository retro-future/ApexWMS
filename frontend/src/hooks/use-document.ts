"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiSend } from "@/lib/api";

/**
 * Documents are not CRUD, so `use-resource.ts` does not fit them: their
 * writes are named acts on a sub-path (`/confirm`, `/cancel`, `/scan`) and
 * every one of them can change the whole document. So each returns the
 * refreshed document, and each invalidates both the list and this item.
 *
 * `resource` is the path segment — "purchase-orders", "receipts".
 */
export function useDocumentAction<TResult, TPayload = void>(
  resource: string,
  id: string,
  {
    method = "POST",
    path,
    invalidate = true,
  }: {
    method?: "POST" | "PATCH" | "DELETE";
    /** Sub-path under the document, or a function of the payload for one that names a row. */
    path: string | ((payload: TPayload) => string);
    /**
     * Off for the scan endpoint: a refetch between beeps costs a round trip
     * the §6 latency budget does not have, and the scan response already
     * carries the accepted unit and the running count.
     */
    invalidate?: boolean;
  },
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: TPayload) =>
      apiSend<TResult>(
        method,
        `/${resource}/${id}${typeof path === "function" ? path(payload) : path}`,
        // A DELETE names its target in the path and carries no body.
        method === "DELETE" ? undefined : (payload ?? {}),
      ),
    // `[resource]` is a prefix of the item key too, so one call covers both.
    onSuccess: invalidate
      ? () => queryClient.invalidateQueries({ queryKey: [resource] })
      : undefined,
  });
}
