# Python Backend Guidelines

## Environment & Commands

- Run everything through `uv run` from `backend/`. Never activate a venv manually or run `python -i`, `pdb`, `ipython`.
- Never start `uv run uvicorn --reload` or any other long-running/blocking process.

## Verification order (before pytest)

Run fast checks on changed files first, in this order:

1. `uv run ruff check <file>`
2. `uv run ty check` (there's no single-file mode; `ty` type-checks the whole `src/` tree, and it's a real gate per root CLAUDE.md, not advisory)
3. `uv run pytest <path_to_test_file> -x -v`

## Testing rules

- Target a specific file or test for routine changes, not the full suite:
  `uv run pytest tests/domain/test_money.py::TestArithmetic::test_add_same_currency`
- Only run the full `uv run pytest` suite when explicitly asked, or before finishing a multi-file change.
- Stop after 2 failed fix attempts on the same error. Report the exact failure to the user instead of continuing to retry.

## Code quality

- Do not add new dependencies to `pyproject.toml` without explicit approval.
