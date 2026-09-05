import json
from pathlib import Path

from loguru import logger

from infrastructure.config import Settings
from infrastructure.logging_config import configure_logging


def test_configure_logging_writes_json_lines_to_the_log_dir(tmp_path: Path) -> None:
    configure_logging(Settings(log_dir=str(tmp_path)))
    logger.bind(foo="bar").info("hello from the test suite")
    logger.remove()  # flush the enqueued file sink before reading it back

    log_file = tmp_path / "app.log"
    assert log_file.is_file()
    line = json.loads(log_file.read_text(encoding="utf-8").splitlines()[-1])
    assert line["record"]["message"] == "hello from the test suite"
    assert line["record"]["extra"]["foo"] == "bar"
