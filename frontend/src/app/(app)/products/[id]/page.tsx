"use client";

import { Alert, Center, Loader } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";

import { ProductForm } from "@/app/(app)/products/ProductForm";
import { useResourceItem } from "@/hooks/use-resource";
import type { Product } from "@/lib/types";

export default function ProductPage() {
  const t = useTranslations("products");
  const params = useParams<{ id: string }>();
  const query = useResourceItem<Product>("products", params.id);

  if (query.isLoading) {
    return (
      <Center p="xl">
        <Loader size="sm" />
      </Center>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
        {query.error instanceof Error ? query.error.message : t("notFound")}
      </Alert>
    );
  }

  return <ProductForm product={query.data} />;
}
