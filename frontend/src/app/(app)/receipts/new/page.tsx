import { Suspense } from "react";

import { ReceiptForm } from "@/app/(app)/receipts/ReceiptForm";
import { RequirePermission } from "@/components/RequirePermission";
import { Permission } from "@/lib/permissions";

/** `useSearchParams` reads `?purchaseOrderId=`, so the form needs a boundary. */
export default function NewReceiptPage() {
  return (
    <RequirePermission permission={Permission.Receiving.Manage}>
      <Suspense>
        <ReceiptForm />
      </Suspense>
    </RequirePermission>
  );
}
