"use client";

import type { UseFormReturnType } from "@mantine/form";
import { useDebouncedValue, useDisclosure } from "@mantine/hooks";
import { useTranslations } from "next-intl";
import { useState } from "react";

import {
  makePageReset,
  useResourceCreate,
  useResourceList,
  useResourceUpdate,
} from "@/hooks/use-resource";
import { ApiError } from "@/lib/api";
import { errorMessage, notifySuccess } from "@/lib/notify";

type Editable = { id: string; isActive: boolean };

/**
 * The shared shape behind every "name plus a few optional fields, paged,
 * searchable, toggle inactive, edit in a modal" list page (suppliers,
 * locations, customers, credit companies): the query/mutation wiring and the
 * open/submit lifecycle, including the 409-on-a-duplicate-name handling.
 * Table columns and form fields stay on each page — those are the part that
 * actually differs between them.
 */
export function useCrudEntityList<T extends Editable, Values extends { isActive: boolean }>(
  resource: string,
  form: UseFormReturnType<Values>,
  options: {
    empty: Values;
    toValues: (item: T) => Values;
    toPayload: (values: Values) => Record<string, unknown>;
    /** Field the form shows a 409 (duplicate name) error on. */
    conflictField: keyof Values & string;
  },
) {
  const tCommon = useTranslations("common");

  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);
  const [showInactive, setShowInactive] = useState(false);
  const [page, setPage] = useState(1);
  const reset = makePageReset(setPage);

  const [opened, modal] = useDisclosure(false);
  const [editing, setEditing] = useState<T | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const query = useResourceList<T>(resource, {
    page,
    search: debouncedSearch || undefined,
    isActive: showInactive ? undefined : true,
  });

  const create = useResourceCreate<T, Record<string, unknown>>(resource);
  const update = useResourceUpdate<T, Record<string, unknown>>(resource);

  function open(item: T | null) {
    setEditing(item);
    setFormError(null);
    form.setValues(item ? options.toValues(item) : options.empty);
    modal.open();
  }

  async function submit(values: Values) {
    setFormError(null);
    const payload = options.toPayload(values);
    try {
      if (editing) {
        await update.mutateAsync({
          id: editing.id,
          payload: { ...payload, isActive: values.isActive },
        });
        notifySuccess(tCommon("updated"));
      } else {
        await create.mutateAsync(payload);
        notifySuccess(tCommon("created"));
      }
      modal.close();
    } catch (err) {
      if (err instanceof ApiError && err.isConflict) {
        form.setFieldError(options.conflictField, err.message);
        return;
      }
      setFormError(errorMessage(err, tCommon("retry")));
    }
  }

  return {
    search,
    onSearchChange: reset(setSearch),
    showInactive,
    onShowInactiveChange: reset(setShowInactive),
    page,
    setPage,
    opened,
    closeModal: modal.close,
    editing,
    formError,
    items: query.data?.items ?? [],
    total: query.data?.totalItems ?? 0,
    pagesCount: query.data?.pagesCount ?? 0,
    isLoading: query.isLoading,
    error: query.error,
    busy: create.isPending || update.isPending,
    open,
    submit,
  };
}
