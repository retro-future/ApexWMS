import httpx
from fastapi import FastAPI

from presentation.middleware import register_request_logging


async def _client() -> httpx.AsyncClient:
    app = FastAPI()
    register_request_logging(app)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_response_carries_a_request_id_header() -> None:
    async with await _client() as client:
        response = await client.get("/ping")
        assert response.status_code == 200
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 36  # uuid4, hyphenated


async def test_each_request_gets_a_different_request_id() -> None:
    async with await _client() as client:
        first = await client.get("/ping")
        second = await client.get("/ping")
        assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]
