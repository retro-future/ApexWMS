"""``JwtTokenService.parse_opaque`` is the reverse of ``issue_refresh``'s
``"{id}.{secret}"`` wire format (``application/dtos/refresh_token_parts.py``).
"""

from datetime import timedelta
from uuid import uuid4

from infrastructure.security.tokens import JwtTokenService
from tests.application.fakes import FakeClock


def _service() -> JwtTokenService:
    return JwtTokenService("test-secret", timedelta(minutes=15), FakeClock())


class TestParseOpaque:
    def test_round_trips_an_issued_refresh_token(self):
        service = _service()
        parts = service.issue_refresh()

        parsed = service.parse_opaque(f"{parts.jti}.{parts.secret}")

        assert parsed == (parts.jti, parts.secret)

    def test_rejects_a_token_with_no_separator(self):
        assert _service().parse_opaque("no-separator") is None

    def test_rejects_an_empty_secret(self):
        assert _service().parse_opaque(f"{uuid4()}.") is None

    def test_rejects_a_non_uuid_id_part(self):
        assert _service().parse_opaque("not-a-uuid.secret") is None
