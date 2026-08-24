import { Suspense } from "react";

import { WriteOffsList } from "@/app/(app)/write-offs/WriteOffsList";

/** The list reads `?status=` off the URL, which needs a boundary to render. */
export default function WriteOffsPage() {
  return (
    <Suspense>
      <WriteOffsList />
    </Suspense>
  );
}
