import { Suspense } from "react";

import { ReceiptsList } from "@/app/(app)/receipts/ReceiptsList";

/** The list reads `?status=` off the URL, which needs a boundary to render. */
export default function ReceiptsPage() {
  return (
    <Suspense>
      <ReceiptsList />
    </Suspense>
  );
}
