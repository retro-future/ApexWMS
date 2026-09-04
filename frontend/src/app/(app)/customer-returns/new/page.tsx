import { CustomerReturnForm } from "@/app/(app)/customer-returns/CustomerReturnForm";
import { RequirePermission } from "@/components/RequirePermission";
import { Permission } from "@/lib/permissions";

export default function NewCustomerReturnPage() {
  return (
    <RequirePermission permission={Permission.CustomerReturn.Manage}>
      <CustomerReturnForm />
    </RequirePermission>
  );
}
