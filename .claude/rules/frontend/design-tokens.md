---
paths:
  - "frontend/src/**/*.tsx"
  - "frontend/src/**/*.ts"
  - "frontend/src/**/*.css"
---

# No hardcoded styling — everything routes through Mantine theme tokens

`frontend/src/theme.ts` is the single source of truth for color, spacing,
typography, radius, and shadow values. A component file should never invent
its own.

## Rules

1. **No inline `style={{ ... }}` for anything a Mantine prop or theme token
   already covers.** If you need custom CSS beyond what style props express
   (e.g. `overflow-x: auto`), write a CSS Module (`Component.module.css`) and
   reference it via `className` — see `src/components/TableScrollArea.tsx`
   for the pattern. Never put a raw color, spacing, or radius value inside a
   `.module.css` file either — use the Mantine CSS custom properties
   (`var(--mantine-color-brand-6)`, `var(--mantine-spacing-md)`, ...).
2. **No hex/rgb color literals in `.tsx`/`.ts`/`.css` files.** Use a theme
   color key (`color="brand"`, `c="dimmed"`, `c="red"`) or a Mantine CSS
   variable. The only place a raw hex value is allowed is inside the 10-shade
   arrays in `theme.ts`'s `colors` block.
3. **No off-scale numeric spacing/typography props** (`gap={2}`, `mt={4}`,
   `fz={28}`, ...). If a design genuinely needs a value outside Mantine's
   default `xs`–`xl` scale, add a named token to `theme.ts` (`spacing`,
   `fontSizes`, `radius`, etc.) and reference it by key, and add the matching
   key to the `MantineThemeSizesOverride` augmentation in
   `src/types/mantine.d.ts`. `gap={0}` / values that mean "no spacing" are
   fine as literals — they're an explicit opt-out, not a magic number.
4. **Raw pixel dimensions are fine for structural sizing**, not design
   tokens: `w={{ base: "100%", sm: 280 }}` on a search input, `maw={720}` on
   a form, `size={16}` on an icon, a `Skeleton`'s placeholder `height`/`width`
   matching real content. These describe layout/content shape, not a design
   choice that should be centrally themeable. Don't force these into
   `theme.ts`. Do, however, hoist a magic number into a named constant (not
   necessarily a theme token) when it's duplicated across files — see
   `ACTIONS_COLUMN_WIDTH` in `src/components/ListShell.tsx`, shared by every
   list page's trailing action column.
5. **Adding a custom color to the theme** means adding it to *both* places:
   the 10-shade array in `theme.ts`'s `colors`, and the
   `MantineThemeColorsOverride` augmentation in `src/types/mantine.d.ts` —
   which must union your new color(s) with Mantine's `DefaultMantineColor`,
   not replace it, or every built-in color name (`"red"`, `"blue"`,
   `"dimmed"`, ...) stops type-checking project-wide.
6. **`MantineProvider` in `src/app/providers.tsx` is the only place `theme`
   is consumed.** Don't construct a second `createTheme()` call or pass
   theme overrides at a component level — extend `theme.ts` instead.
7. **Don't add `"use client"` to make styling changes.** Style props, theme
   tokens, and CSS Modules all work in Server Components. Only add it when
   the component genuinely needs interactivity/hooks.

## Why

Centralizing tokens means a rebrand or a dark-mode contrast fix is a
`theme.ts` diff, not a grep-and-replace across every page. It also keeps
`ty`-style guarantees on the frontend: the `MantineThemeSizesOverride` /
`MantineThemeColorsOverride` augmentations make an invalid token name a
compile error (`pnpm run typecheck`) instead of a silent visual bug.
