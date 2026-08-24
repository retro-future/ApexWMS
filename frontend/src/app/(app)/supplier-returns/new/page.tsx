import { SupplierReturnForm } from "@/app/(app)/supplier-returns/SupplierReturnForm";
import { RequirePermission } from "@/components/RequirePermission";
import { Permission } from "@/lib/permissions";

export default function NewSupplierReturnPage() {
  return (
    <RequirePermission permission={Permission.SupplierReturn.Manage}>
      <SupplierReturnForm />
    </RequirePermission>
  );
}
