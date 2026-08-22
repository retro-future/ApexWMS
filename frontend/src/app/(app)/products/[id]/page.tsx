"use client";

import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";

import { ProductForm } from "@/app/(app)/products/ProductForm";
import { DetailError, DetailLoading } from "@/components/DetailStates";
import { useResourceItem } from "@/hooks/use-resource";
import type { Product } from "@/lib/types";

export default function ProductPage() {
  const t = useTranslations("products");
  const params = useParams<{ id: string }>();
  const query = useResourceItem<Product>("products", params.id);

  if (query.isLoading) return <DetailLoading />;

  if (query.isError || !query.data) {
    return (
      <DetailError
        message={query.error instanceof Error ? query.error.message : t("notFound")}
      />
    );
  }

  return <ProductForm product={query.data} />;
}
