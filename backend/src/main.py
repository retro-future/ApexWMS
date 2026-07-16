"""Entry point: `uv run uvicorn main:app --reload` (from backend/)."""

from presentation.app import create_app

app = create_app()
