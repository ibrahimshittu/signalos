from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from signalos_backend.macro.bls import BlsClient, BlsProviderError


async def test_bls_client_normalizes_latest_cpi_and_release_calendar() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/CUUR0000SA0"):
            assert request.url.params["latest"] == "true"
            return httpx.Response(
                200,
                json={
                    "status": "REQUEST_SUCCEEDED",
                    "message": [],
                    "Results": {
                        "series": [
                            {
                                "seriesID": "CUUR0000SA0",
                                "data": [
                                    {
                                        "year": "2026",
                                        "period": "M08",
                                        "periodName": "August",
                                        "latest": "true",
                                        "value": "325.252",
                                        "footnotes": [{}],
                                    }
                                ],
                            }
                        ]
                    },
                },
            )
        return httpx.Response(
            200,
            text=(
                "BEGIN:VCALENDAR\r\n"
                "BEGIN:VEVENT\r\n"
                "DTSTART;TZID=US-Eastern:20261014T083000\r\n"
                "SUMMARY:Consumer Price Index\r\n"
                "UID:cpi-2026-10@bls.gov\r\n"
                "END:VEVENT\r\n"
                "END:VCALENDAR\r\n"
            ),
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BlsClient(
        http=http,
        api_base_url="https://api.bls.test/publicAPI/v2",
        calendar_url="https://www.bls.test/bls.ics",
        clock=lambda: datetime(2026, 9, 21, 12, tzinfo=UTC),
    )

    observation = await client.latest_cpi()
    releases = await client.cpi_releases()

    assert observation.series_id == "CUUR0000SA0"
    assert observation.reference_period == "2026-08"
    assert observation.value == Decimal("325.252")
    assert observation.retrieved_at == datetime(2026, 9, 21, 12, tzinfo=UTC)
    assert releases[0].external_id == "cpi-2026-10@bls.gov"
    assert releases[0].scheduled_at == datetime(2026, 10, 14, 12, 30, tzinfo=UTC)
    await http.aclose()


async def test_bls_client_rejects_unsuccessful_or_malformed_payloads() -> None:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"status": "REQUEST_FAILED", "message": ["rate limit"], "Results": {}},
            )
        )
    )
    client = BlsClient(http=http, api_base_url="https://api.bls.test/publicAPI/v2")

    with pytest.raises(BlsProviderError, match="rate limit"):
        await client.latest_cpi()
    await http.aclose()
