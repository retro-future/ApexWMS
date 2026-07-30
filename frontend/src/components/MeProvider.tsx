"use client";

import { createContext, useContext, useMemo } from "react";

import { can } from "@/lib/permissions";
import type { Me } from "@/lib/types";

/**
 * `me` is fetched once, server-side, in the app layout and handed down. No
 * client fetch, so no loading flicker and no second round trip for something
 * that cannot change mid-page.
 */
const MeContext = createContext<Me | null>(null);

export function MeProvider({
  me,
  children,
}: {
  me: Me;
  children: React.ReactNode;
}) {
  return <MeContext.Provider value={me}>{children}</MeContext.Provider>;
}

export function useMe(): Me {
  const me = useContext(MeContext);
  if (!me) throw new Error("useMe() used outside of <MeProvider>");
  return me;
}

/** `const can = useCan(); can(Permission.Catalog.Manage)` */
export function useCan(): (permission: string) => boolean {
  const me = useMe();
  return useMemo(() => (permission: string) => can(me, permission), [me]);
}
