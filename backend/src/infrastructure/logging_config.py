"""Process-wide logging setup (loguru).

Called once from the composition root (``presentation/app.py``), not wired
through Dishka — configuring global log sinks is a side effect, not
something to construct per-request.
"""

import sys
from pathlib import Path

from loguru import logger

from infrastructure.config import Settings


def configure_logging(settings: Settings) -> None:
    logger.remove()

    console_level = "DEBUG" if settings.debug else settings.log_level
    logger.add(
        sys.stderr,
        level=console_level,
        colorize=True,
    )

    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "app.log",
        level=settings.log_level,
        rotation="00:00",
        retention="7 days",
        serialize=True,
        enqueue=True,
    )
