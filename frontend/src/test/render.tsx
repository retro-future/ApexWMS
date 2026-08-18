import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";

import messages from "../../messages/en.json";
import { MeProvider } from "@/components/MeProvider";
import { theme } from "@/theme";
import type { Me, TenantRole } from "@/lib/types";

/**
 * The four providers every screen sits inside. Real ones rather than mocks:
 * a component test that stubs out the theme or the translations stops
 * proving anything about what the operator sees.
 */
export function makeMe(permissions: string[], role: TenantRole = "tenant.owner"): Me {
  return {
    userId: "user-1",
    email: "owner@example.com",
    fullName: "Test Owner",
    mustChangePassword: false,
    tenantId: "tenant-1",
    role,
    appRoles: [],
    permissions,
  };
}

export function renderWithProviders(
  ui: React.ReactElement,
  { me = makeMe([]), ...options }: RenderOptions & { me?: Me } = {},
) {
  const queryClient = new QueryClient({
    // A failed request in a test is the assertion, not something to retry.
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(ui, {
    wrapper: ({ children }) => (
      <NextIntlClientProvider locale="en" messages={messages}>
        <MantineProvider theme={theme} env="test">
          <QueryClientProvider client={queryClient}>
            <MeProvider me={me}>{children}</MeProvider>
          </QueryClientProvider>
        </MantineProvider>
      </NextIntlClientProvider>
    ),
    ...options,
  });
}
