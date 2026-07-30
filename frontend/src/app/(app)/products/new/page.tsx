"use client";

import { Alert } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { ProductForm } from "@/app/(app)/products/ProductForm";
import { useCan } from "@/components/MeProvider";
import { Permission } from "@/lib/permissions";

export default function NewProductPage() {
  const t = useTranslations("errors");
  const can = useCan();

  // The nav hides the button, but a pasted URL should say why, not 403 later.
  if (!can(Permission.Catalog.Manage)) {
    return (
      <Alert variant="light" color="red" icon={<IconAlertCircle size={18} />}>
        {t("forbidden")}
      </Alert>
    );
  }

  return <ProductForm />;
}
