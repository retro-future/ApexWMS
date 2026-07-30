import type { TenantRole } from "@/lib/types";

/**
 * Roles are namespaced on the wire ("tenant.owner") to keep them from ever
 * colliding with app roles ("app.superadmin"). Message catalogs key on the
 * bare name.
 */
export function roleLabelKey(role: TenantRole): string {
  return role.replace("tenant.", "");
}
