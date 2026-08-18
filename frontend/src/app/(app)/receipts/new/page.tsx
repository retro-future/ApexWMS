import { Suspense } from "react";

import { ReceiptForm } from "@/app/(app)/receipts/ReceiptForm";

/** `useSearchParams` reads `?purchaseOrderId=`, so the form needs a boundary. */
export default function NewReceiptPage() {
  return (
    <Suspense>
      <ReceiptForm />
    </Suspense>
  );
}
