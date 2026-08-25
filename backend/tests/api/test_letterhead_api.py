"""The store's own details on its paperwork (PRD §5.8, FR-8.1).

The logo is the piece that needed somewhere to live. It goes in the
tenant's own settings row as bytes, so these tests are about the round trip
— upload, read back, clear — and about the image reaching an actual page.
"""

import base64

import pytest

from tests.api.ledger_helpers import PASSWORD
from tests.api.pdf_helpers import PNG_BASE64

API = "/api/v1"

# A GIF: a real image, and one neither fpdf2's letterhead nor this API
# accepts, so it stands in for "the wrong sort of file".
GIF_BASE64 = base64.b64encode(
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
).decode()


@pytest.fixture
async def owner(create_tenant):
    return await create_tenant(password=PASSWORD)


class TestTheLogoRoundTrips:
    async def test_upload_read_back_and_clear(self, client, owner):
        set_up = await client.put(
            f"{API}/settings/tenant/logo",
            headers=owner.auth,
            json={"content": PNG_BASE64},
        )
        assert set_up.status_code == 200, set_up.text
        assert set_up.json()["data"]["hasLogo"] is True

        fetched = await client.get(f"{API}/settings/tenant/logo", headers=owner.auth)
        assert fetched.status_code == 200, fetched.text
        assert fetched.headers["content-type"] == "image/png"
        assert fetched.content == base64.b64decode(PNG_BASE64)

        cleared = await client.put(
            f"{API}/settings/tenant/logo", headers=owner.auth, json={}
        )
        assert cleared.json()["data"]["hasLogo"] is False
        assert (
            await client.get(f"{API}/settings/tenant/logo", headers=owner.auth)
        ).status_code == 404

    async def test_a_settings_write_does_not_drop_the_logo(self, client, owner):
        """The two are set through different routes and must not collide."""
        await client.put(
            f"{API}/settings/tenant/logo",
            headers=owner.auth,
            json={"content": PNG_BASE64},
        )

        written = await client.put(
            f"{API}/settings/tenant",
            headers=owner.auth,
            json={"timezone": "Asia/Tashkent", "businessName": "Apex Mobile"},
        )

        assert written.json()["data"]["hasLogo"] is True
        assert (
            await client.get(f"{API}/settings/tenant/logo", headers=owner.auth)
        ).status_code == 200

    async def test_no_logo_is_a_404_not_an_empty_200(self, client, owner):
        missing = await client.get(f"{API}/settings/tenant/logo", headers=owner.auth)

        assert missing.status_code == 404, missing.text


class TestWhatIsRefused:
    @pytest.mark.parametrize(
        ("content", "why"),
        [
            ("not base64 at all!!", "not base64"),
            (base64.b64encode(b"just some text").decode(), "not an image"),
            (GIF_BASE64, "an image, but not one that prints"),
        ],
    )
    async def test_a_bad_upload_is_refused(self, client, owner, content, why):
        refused = await client.put(
            f"{API}/settings/tenant/logo",
            headers=owner.auth,
            json={"content": content},
        )

        assert refused.status_code == 422, f"{why}: {refused.text}"
        settings = await client.get(f"{API}/settings/tenant", headers=owner.auth)
        assert settings.json()["data"]["hasLogo"] is False

    async def test_an_image_past_the_size_cap_is_refused(self, client, owner):
        oversized = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * (512 * 1024))

        refused = await client.put(
            f"{API}/settings/tenant/logo",
            headers=owner.auth,
            json={"content": oversized.decode()},
        )

        assert refused.status_code == 422, refused.text
