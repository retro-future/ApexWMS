import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Unit tests only: pure logic (money, receipt derivations) and components
 * whose behaviour is worth pinning down, like the scan console's focus
 * handling. The API is exercised by the backend's own suite, so nothing
 * here talks to a server.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    // Mirrors the `@/*` path alias in tsconfig.json.
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
