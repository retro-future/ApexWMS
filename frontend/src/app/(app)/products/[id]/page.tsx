"use client";

import { Button, Group, Stack } from "@mantine/core";
import { IconShoppingCart } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ProductCodeActions } from "@/app/(app)/products/ProductCodeActions";
import { ProductForm } from "@/app/(app)/products/ProductForm";
import { SellAccessoryModal } from "@/app/(app)/products/SellAccessoryModal";
import { DetailError, DetailLoading } from "@/components/DetailStates";
import { useCan } from "@/components/MeProvider";
import { useResourceItem } from "@/hooks/use-resource";
import { Permission } from "@/lib/permissions";
import type { Product } from "@/lib/types";

export default function ProductPage() {
  const t = useTranslations("products");
  const tSell = useTranslations("invoices.sell");
  const params = useParams<{ id: string }>();
  const can = useCan();
  const query = useResourceItem<Product>("products", params.id);
  const [selling, setSelling] = useState(false);

  if (query.isLoading) return <DetailLoading />;

  if (query.isError || !query.data) {
    return (
      <DetailError
        message={query.error instanceof Error ? query.error.message : t("notFound")}
      />
    );
  }

  const product = query.data;
  const canSell =
    product.trackingType === "quantity" &&
    product.isActive &&
    can(Permission.Sales.Manage);

  return (
    <Stack gap="lg">
      {canSell && (
        <Group>
          <Button
            leftSection={<IconShoppingCart size={16} />}
            onClick={() => setSelling(true)}
          >
            {tSell("sellAccessory")}
          </Button>
        </Group>
      )}
      <ProductForm product={product} />
      <ProductCodeActions product={product} />
      {selling && (
        <SellAccessoryModal product={product} onClose={() => setSelling(false)} />
      )}
    </Stack>
  );
}
