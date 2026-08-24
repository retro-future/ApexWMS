# Next.js Frontend Guidelines

## Environment & Commands

- Package manager is `pnpm` (see `pnpm-lock.yaml`). Run everything from `frontend/`.
- Never start `pnpm dev` / `next dev` or any other persistent dev server.

## Verification order (before tests)

Run fast checks on changed files first, in this order:

1. `npx eslint <file>` (flat config at `eslint.config.mjs`), or `pnpm lint` for the whole project
2. `pnpm typecheck` (`tsc --noEmit`)
3. `pnpm test <path_to_test_file>` (vitest, e.g. `pnpm test src/lib/money.test.ts`)

## Testing rules

- Vitest runs single-shot by default here (`"test": "vitest run"`). Never pass `--watch`.
- Target a specific test file for routine changes, not the full suite.
- Stop after 2 failed fix attempts on the same error. Report the exact failure to the user instead of continuing to retry.

## Code quality

- Do not add new packages without explicit approval.
