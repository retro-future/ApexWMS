import { Suspense } from "react";

import { SupplierReturnsList } from "@/app/(app)/supplier-returns/SupplierReturnsList";

/** The list reads `?status=` off the URL, which needs a boundary to render. */
export default function SupplierReturnsPage() {
  return (
    <Suspense>
      <SupplierReturnsList />
    </Suspense>
  );
}
