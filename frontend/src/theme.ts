"use client";

import { createTheme, rem } from "@mantine/core";

export const theme = createTheme({
  colors: {
    // Same 10 shades as Mantine's built-in "indigo" — named "brand" so the
    // rest of the app never has to know which base hue we picked.
    brand: [
      "#edf2ff",
      "#dbe4ff",
      "#bac8ff",
      "#91a7ff",
      "#748ffc",
      "#5c7cfa",
      "#4c6ef5",
      "#4263eb",
      "#3b5bdb",
      "#364fc7",
    ],
  },
  primaryColor: "brand",
  defaultRadius: "md",
  fontFamily:
    "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  headings: {
    fontWeight: "600",
  },
  cursorType: "pointer",
  spacing: {
    // Below the default scale (xs = 10px): tight label/value stacks like a
    // page title over its subtitle, or a name over a badge row.
    "3xs": rem(2),
    "2xs": rem(4),
  },
  fontSizes: {
    // Above the default scale (xl = 20px): headline stat numbers on the
    // dashboard cards.
    "2xl": rem(28),
  },
});
