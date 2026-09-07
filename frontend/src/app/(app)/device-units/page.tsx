import { DeviceInventoryList } from "@/app/(app)/device-units/DeviceInventoryList";
import { RequirePermission } from "@/components/RequirePermission";
import { Permission } from "@/lib/permissions";

export default function DeviceInventoryPage() {
  return (
    <RequirePermission permission={Permission.Reporting.View}>
      <DeviceInventoryList />
    </RequirePermission>
  );
}
