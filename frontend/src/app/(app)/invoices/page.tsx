import { Suspense } from "react";

import { InvoicesList } from "@/app/(app)/invoices/InvoicesList";

/** The list reads `?status=` off the URL, which needs a boundary to render. */
export default function InvoicesPage() {
  return (
    <Suspense>
      <InvoicesList />
    </Suspense>
  );
}
