import { Suspense } from "react";

import { StockCountsList } from "@/app/(app)/stock-counts/StockCountsList";

/** The list reads `?status=` off the URL, which needs a boundary to render. */
export default function StockCountsPage() {
  return (
    <Suspense>
      <StockCountsList />
    </Suspense>
  );
}
