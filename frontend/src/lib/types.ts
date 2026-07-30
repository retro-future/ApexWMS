/**
 * The slice of the backend's wire contract this frontend actually uses.
 *
 * Hand-written rather than generated so the app typechecks without a running
 * backend. `pnpm gen:api` regenerates the full OpenAPI schema into
 * src/lib/schema.d.ts if you ever want to cross-check these by hand.
 *
 * Everything is camelCase: every backend model inherits CamelModel.
 */

export type TenantRole =
  | "tenant.owner"
  | "tenant.manager"
  | "tenant.storekeeper"
  | "tenant.seller";

export const TENANT_ROLES: TenantRole[] = [
  "tenant.owner",
  "tenant.manager",
  "tenant.storekeeper",
  "tenant.seller",
];

export type AppRole = "app.superadmin" | "app.admin";

export type TrackingType = "serial" | "quantity";

export type Currency = "UZS" | "USD";

/** GET /auth/me */
export type Me = {
  userId: string;
  email: string;
  fullName: string;
  mustChangePassword: boolean;
  tenantId?: string | null;
  role?: TenantRole | null;
  appRoles: AppRole[];
  permissions: string[];
};

/** What POST /api/auth/login hands back to the browser — never the tokens. */
export type LoginResult = {
  mustChangePassword: boolean;
  tenantId: string | null;
  role: TenantRole | null;
  appRoles: AppRole[];
};

export type Product = {
  id: string;
  sku: string;
  name: string;
  brand: string | null;
  model: string | null;
  trackingType: TrackingType;
  currency: Currency;
  barcode: string | null;
  /** Exact major units as a string, e.g. "599.00". Never a float. */
  defaultSalePrice: string | null;
  /** The integer actually stored. Meaningless without `currency`. */
  defaultSalePriceMinor: number | null;
  isActive: boolean;
};

export type Location = {
  id: string;
  name: string;
  isActive: boolean;
};

export type Supplier = {
  id: string;
  name: string;
  contactName: string | null;
  phone: string | null;
  email: string | null;
  isActive: boolean;
};

export type Customer = {
  id: string;
  fullName: string;
  phone: string | null;
  isActive: boolean;
};

/** GET /users — note this one is NOT paged. */
export type Employee = {
  id: string;
  email: string;
  fullName: string;
  role: TenantRole;
  isActive: boolean;
};

/** POST /users/invite */
export type InviteResult = {
  invitationId: string;
  /** Wire format "{invitationId}.{secret}". No email is sent. */
  token: string;
  expiresAt: string;
};

export type TenantSettings = {
  timezone: string;
};
