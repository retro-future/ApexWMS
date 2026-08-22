"use client";

import { useRouter } from "next/navigation";

/** Drops the session cookies and sends the browser to `destination`. */
export function useSignOut() {
  const router = useRouter();

  return async function signOut(destination = "/login") {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace(destination);
    router.refresh();
  };
}
