import "@mantine/core";

/**
 * Extends Mantine's theme-driven prop types with this project's tokens, so
 * `color="brand"`, `gap="3xs"`, and `fz="2xl"` type-check the same way the
 * built-in scale keys do. Values live in `src/theme.ts`; this file only
 * teaches the type system about the keys.
 */
declare module "@mantine/core" {
  export interface MantineThemeColorsOverride {
    colors: Record<"brand" | DefaultMantineColor, MantineColorsTuple>;
  }

  export interface MantineThemeSizesOverride {
    spacing: {
      xs: string;
      sm: string;
      md: string;
      lg: string;
      xl: string;
      "3xs": string;
      "2xs": string;
    };
    fontSizes: {
      xs: string;
      sm: string;
      md: string;
      lg: string;
      xl: string;
      "2xl": string;
    };
  }
}
