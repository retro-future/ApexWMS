import { ProductForm } from "@/app/(app)/products/ProductForm";
import { RequirePermission } from "@/components/RequirePermission";
import { Permission } from "@/lib/permissions";

export default function NewProductPage() {
  return (
    <RequirePermission permission={Permission.Catalog.Manage}>
      <ProductForm />
    </RequirePermission>
  );
}
