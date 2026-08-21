"""FR-9.7's price-deviations report, against real tables — PRD §5.9.

The report answers *"who keeps discounting, and for whom?"*, so what these
tests pin down is attribution: the approver survives onto the row even
though a different person confirmed the invoice, and a sale **above** the
asking price is reported just as readily as one below it.
"""

from tests.api.ledger_helpers import receive_phone

PHONE_IMEI = "490154203237518"


async def sell(client, settings, owner, *, asking: str, charged: str | None, note=None):
    """Put a handset in stock at *asking*, sell it, optionally overridden."""
    unit_id, _, location_id = await receive_phone(client, settings, owner)
    await client.patch(
        f"/api/v1/device-units/{unit_id}/price",
        headers=owner.auth,
        json={"askingPrice": asking, "reason": "priced for sale"},
    )
    created = await client.post(
        "/api/v1/invoices", headers=owner.auth, json={"locationId": str(location_id)}
    )
    invoice_id = created.json()["data"]["id"]
    scanned = await client.post(
        f"/api/v1/invoices/{invoice_id}/scan",
        headers=owner.auth,
        json={"code": PHONE_IMEI},
    )
    line_id = scanned.json()["data"]["line"]["id"]

    if charged is not None:
        overridden = await client.patch(
            f"/api/v1/invoices/{invoice_id}/lines/{line_id}",
            headers=owner.auth,
            json={"price": charged, "note": note},
        )
        assert overridden.status_code == 200, overridden.text

    confirmed = await client.post(
        f"/api/v1/invoices/{invoice_id}/confirm", headers=owner.auth
    )
    assert confirmed.status_code == 200, confirmed.text
    return invoice_id


async def deviations(client, auth, **params):
    response = await client.get(
        "/api/v1/reports/price-deviations", headers=auth, params=params
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestADiscountIsReportedWithItsApprover:
    async def test_the_row_carries_both_prices_the_handset_and_the_note(
        self, client, settings, owner
    ):
        invoice_id = await sell(
            client, settings, owner, asking="520", charged="300", note="haggled hard"
        )

        body = await deviations(client, owner.auth)

        assert body["totalItems"] == 1
        row = body["data"][0]
        assert row["invoiceId"] == invoice_id
        assert row["resolvedPriceMinor"] == 52000
        assert row["chargedPriceMinor"] == 30000
        assert row["differenceMinor"] == -22000
        assert row["priceApprovedBy"] == owner.user_id
        assert row["priceNote"] == "haggled hard"
        assert row["imei"] == PHONE_IMEI
        assert row["currency"] == "USD"


class TestASaleAboveTheAskingPriceIsReportedToo:
    """FR-9.7 reports deviations in *both* directions."""

    async def test_the_difference_is_positive_and_the_row_is_present(
        self, client, settings, owner
    ):
        await sell(client, settings, owner, asking="520", charged="600")

        body = await deviations(client, owner.auth)

        assert body["totalItems"] == 1
        assert body["data"][0]["differenceMinor"] == 8000


class TestALineChargedWhatWasResolvedIsNotADeviation:
    async def test_an_un_overridden_sale_does_not_appear(
        self, client, settings, owner
    ):
        await sell(client, settings, owner, asking="520", charged=None)

        body = await deviations(client, owner.auth)

        assert body["totalItems"] == 0
        assert body["data"] == []

    async def test_nor_does_an_override_that_matches_the_resolved_price(
        self, client, settings, owner
    ):
        """The override is real; the deviation is not."""
        await sell(client, settings, owner, asking="520", charged="520")

        body = await deviations(client, owner.auth)

        assert body["totalItems"] == 0


class TestACancelledSaleLeavesTheReport:
    """A reversed sale is not a deviation anyone still has to answer for,
    even though the line keeps its snapshot (§4.4)."""

    async def test_cancelling_removes_the_row(self, client, settings, owner):
        invoice_id = await sell(client, settings, owner, asking="520", charged="300")
        assert (await deviations(client, owner.auth))["totalItems"] == 1

        cancelled = await client.post(
            f"/api/v1/invoices/{invoice_id}/cancel", headers=owner.auth, json={}
        )
        assert cancelled.status_code == 200, cancelled.text

        assert (await deviations(client, owner.auth))["totalItems"] == 0


class TestFiltering:
    async def test_an_approver_who_approved_nothing_matches_no_rows(
        self, client, settings, owner
    ):
        await sell(client, settings, owner, asking="520", charged="300")

        body = await deviations(
            client, owner.auth, approvedBy="00000000-0000-0000-0000-000000000001"
        )

        assert body["totalItems"] == 0

    async def test_the_approver_who_did_matches(self, client, settings, owner):
        await sell(client, settings, owner, asking="520", charged="300")

        body = await deviations(client, owner.auth, approvedBy=owner.user_id)

        assert body["totalItems"] == 1


class TestWhoMayRead:
    """§2.1: reporting is Manager and Owner. A Seller sees prices on the
    invoice they are ringing up, not the store's discount pattern."""

    async def test_a_seller_is_refused(self, client, settings, owner):
        await sell(client, settings, owner, asking="520", charged="300")

        invite = await client.post(
            "/api/v1/users/invite",
            headers=owner.auth,
            json={"email": "seller@example.com", "role": "tenant.seller"},
        )
        await client.post(
            "/api/v1/auth/accept-invite",
            json={"token": invite.json()["data"]["token"], "password": "sellerpass1"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "seller@example.com", "password": "sellerpass1"},
        )
        seller = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

        refused = await client.get(
            "/api/v1/reports/price-deviations", headers=seller
        )

        assert refused.status_code == 403
