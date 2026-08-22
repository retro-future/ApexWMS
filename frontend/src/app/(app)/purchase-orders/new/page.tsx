import { PurchaseOrderForm } from "@/app/(app)/purchase-orders/PurchaseOrderForm";
import { RequirePermission } from "@/components/RequirePermission";
import { Permission } from "@/lib/permissions";

export default function NewPurchaseOrderPage() {
  return (
    <RequirePermission permission={Permission.PurchaseOrder.Manage}>
      <PurchaseOrderForm />
    </RequirePermission>
  );
}
