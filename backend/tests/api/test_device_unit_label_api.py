"""A handset's IMEI label as a PDF — FR-8.1, end to end.

Runs the whole stack against a migrated Postgres, so this proves the DI
wiring and that the renderer reaches ``python-barcode``.
"""

from uuid import uuid4

from tests.api.ledger_helpers import PHONE_IMEI, receive_phone
from tests.api.pdf_helpers import pdf_text


class TestDeviceUnitLabel:
    async def test_the_label_encodes_the_units_imei(self, client, settings, owner):
        unit_id, _, _ = await receive_phone(client, settings, owner)

        resp = await client.get(
            f"/api/v1/device-units/{unit_id}/label.pdf", headers=owner.auth
        )

        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content.startswith(b"%PDF")
        page = pdf_text(resp.content)
        assert PHONE_IMEI in page
        assert "iPhone 15 Pro" in page

    async def test_a_sheet_of_copies_still_renders(self, client, settings, owner):
        unit_id, _, _ = await receive_phone(client, settings, owner)

        resp = await client.get(
            f"/api/v1/device-units/{unit_id}/label.pdf?layout=sheet&copies=4",
            headers=owner.auth,
        )

        assert resp.status_code == 200, resp.text
        assert PHONE_IMEI in pdf_text(resp.content)

    async def test_an_unknown_unit_has_no_label(self, client, owner):
        resp = await client.get(
            f"/api/v1/device-units/{uuid4()}/label.pdf", headers=owner.auth
        )

        assert resp.status_code == 404, resp.text
