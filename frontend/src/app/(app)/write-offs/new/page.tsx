import { WriteOffForm } from "@/app/(app)/write-offs/WriteOffForm";
import { RequirePermission } from "@/components/RequirePermission";
import { Permission } from "@/lib/permissions";

export default function NewWriteOffPage() {
  return (
    <RequirePermission permission={Permission.WriteOff.Manage}>
      <WriteOffForm />
    </RequirePermission>
  );
}
