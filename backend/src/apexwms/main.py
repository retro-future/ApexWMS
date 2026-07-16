"""Entry point: `uv run uvicorn apexwms.main:app --reload` (from backend/)."""

from apexwms.presentation.app import create_app

app = create_app()
