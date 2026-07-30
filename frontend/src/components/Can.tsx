"use client";

import { useCan } from "@/components/MeProvider";

/** Renders children only if the signed-in user holds the permission. */
export function Can({
  permission,
  fallback = null,
  children,
}: {
  permission: string;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}) {
  const can = useCan();
  return <>{can(permission) ? children : fallback}</>;
}
