import { StockCountForm } from "@/app/(app)/stock-counts/StockCountForm";
import { RequirePermission } from "@/components/RequirePermission";
import { Permission } from "@/lib/permissions";

export default function NewStockCountPage() {
  return (
    <RequirePermission permission={Permission.StockCount.Run}>
      <StockCountForm />
    </RequirePermission>
  );
}
