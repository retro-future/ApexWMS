import { Suspense } from "react";

import { CustomerReturnsList } from "@/app/(app)/customer-returns/CustomerReturnsList";

/** The list reads `?status=` off the URL, which needs a boundary to render. */
export default function CustomerReturnsPage() {
  return (
    <Suspense>
      <CustomerReturnsList />
    </Suspense>
  );
}
