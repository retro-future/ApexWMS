/**
 * The permission strings this frontend gates on, mirrored from the backend's
 * domain/permissions.py. Only the M2-relevant subset is listed.
 *
 * Gate on permissions, never on role names: PRD §2.1's matrix is not
 * hierarchical, so there is no rank to compare. A Storekeeper can receive
 * goods but not sell; a Seller can sell but not receive. Neither outranks
 * the other.
 *
 * And remember the UI is not the enforcement point — the server checks every
 * request regardless. Hiding a button is a courtesy, not a permission.
 */

import type { Me } from "@/lib/types";

export const Permission = {
  Catalog: {
    View: "Permission.Catalog.View",
    Manage: "Permission.Catalog.Manage",
  },
  Location: {
    View: "Permission.Location.View",
    Manage: "Permission.Location.Manage",
  },
  Customer: {
    View: "Permission.Customer.View",
    Manage: "Permission.Customer.Manage",
  },
  Users: {
    View: "Permission.Users.View",
    Manage: "Permission.Users.Manage",
  },
  TenantSettings: {
    View: "Permission.TenantSettings.View",
    Manage: "Permission.TenantSettings.Manage",
  },
  Cost: {
    View: "Permission.Cost.View",
  },
} as const;

export function can(me: Me | null | undefined, permission: string): boolean {
  return Boolean(me?.permissions?.includes(permission));
}

export function canAny(
  me: Me | null | undefined,
  permissions: string[],
): boolean {
  return permissions.some((permission) => can(me, permission));
}
