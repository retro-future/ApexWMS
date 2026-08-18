"use client";

import { Select } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { useState } from "react";

import { useResourceList } from "@/hooks/use-resource";
import type { Product } from "@/lib/types";

/**
 * A server-filtered product picker, shared by the two document forms.
 *
 * It hands the whole `Product` back rather than an id, because every caller
 * immediately needs two more things off it: the currency the line's amounts
 * are denominated in (§4.5 rule 3) and the tracking type that decides
 * whether the line is scanned or counted (§4.1).
 */
export function ProductSelect({
  value,
  onChange,
  label,
  placeholder,
  error,
  disabled,
}: {
  value: string | null;
  onChange: (product: Product | null) => void;
  label?: string;
  placeholder?: string;
  error?: React.ReactNode;
  disabled?: boolean;
}) {
  const [search, setSearch] = useState("");
  const [debounced] = useDebouncedValue(search, 300);

  const query = useResourceList<Product>("products", {
    page: 1,
    pageSize: 50,
    search: debounced || undefined,
    // A deactivated product cannot be bought or received (FR-2.4).
    isActive: true,
  });

  const products = query.data?.items ?? [];

  return (
    <Select
      label={label}
      placeholder={placeholder}
      value={value}
      onChange={(id) => onChange(products.find((p) => p.id === id) ?? null)}
      data={products.map((product) => ({
        value: product.id,
        label: `${product.name} · ${product.sku}`,
      }))}
      searchable
      searchValue={search}
      onSearchChange={setSearch}
      nothingFoundMessage={query.isLoading ? undefined : "—"}
      error={error}
      disabled={disabled}
      // The search is server-side; filtering the page again client-side would
      // hide rows the server already decided match.
      filter={({ options }) => options}
    />
  );
}
