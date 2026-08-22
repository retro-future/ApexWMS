import { InvoiceForm } from "@/app/(app)/invoices/InvoiceForm";
import { RequirePermission } from "@/components/RequirePermission";
import { Permission } from "@/lib/permissions";

export default function NewInvoicePage() {
  return (
    <RequirePermission permission={Permission.Sales.Manage}>
      <InvoiceForm />
    </RequirePermission>
  );
}
