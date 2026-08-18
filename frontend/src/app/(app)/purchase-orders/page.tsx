import { Suspense } from "react";

import { PurchaseOrdersList } from "@/app/(app)/purchase-orders/PurchaseOrdersList";

/** The list reads `?status=` off the URL, which needs a boundary to render. */
export default function PurchaseOrdersPage() {
  return (
    <Suspense>
      <PurchaseOrdersList />
    </Suspense>
  );
}
