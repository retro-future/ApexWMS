import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const nextConfig: NextConfig = {
  // Ships a self-contained server bundle (.next/standalone) for the Docker image.
  output: "standalone",
  // Lets the dev server serve phones/tablets on the LAN (e.g. testing login
  // on a real device) instead of silently blocking RSC/navigation requests.
  // The ngrok-free.app wildcard covers the free-tier random subdomain that
  // changes on every `ngrok http` restart.
  allowedDevOrigins: ["192.168.100.8", "*.ngrok-free.app", "*.ngrok.io", "*.ngrok.app"],
};

// Picks up src/i18n/request.ts by convention.
const withNextIntl = createNextIntlPlugin();

export default withNextIntl(nextConfig);
