from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from signalos_backend.domain import utc_now
from signalos_backend.macro.domain import MacroObservation, MacroRelease

CPI_SERIES_ID = "CUUR0000SA0"
CPI_SOURCE_URL = "https://www.bls.gov/cpi/"
CPI_CALENDAR_SOURCE_URL = "https://www.bls.gov/schedule/news_release/cpi.htm"


class BlsProviderError(RuntimeError):
    """BLS returned an unusable response."""


class _BlsPoint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    year: str = Field(pattern=r"^\d{4}$")
    period: str = Field(pattern=r"^M(0[1-9]|1[0-2])$")
    value: str


class _BlsSeries(BaseModel):
    model_config = ConfigDict(extra="ignore")

    seriesID: str
    data: list[_BlsPoint]


class _BlsResults(BaseModel):
    model_config = ConfigDict(extra="ignore")

    series: list[_BlsSeries] = Field(default_factory=list)


class _BlsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
    message: list[str] = Field(default_factory=list)
    Results: _BlsResults | None = None


class BlsClient:
    def __init__(
        self,
        *,
        http: httpx.AsyncClient | None = None,
        api_base_url: str = "https://api.bls.gov/publicAPI/v2",
        calendar_url: str = "https://www.bls.gov/schedule/news_release/bls.ics",
        timeout_seconds: float = 10,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.http = http or httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={"User-Agent": "SignalOS/0.1 official-data-client"},
        )
        self._owns_http = http is None
        self.api_base_url = api_base_url.rstrip("/")
        self.calendar_url = calendar_url
        self.clock = clock

    async def close(self) -> None:
        if self._owns_http:
            await self.http.aclose()

    async def latest_cpi(self) -> MacroObservation:
        try:
            response = await self.http.get(
                f"{self.api_base_url}/timeseries/data/{CPI_SERIES_ID}",
                params={"latest": "true"},
            )
            response.raise_for_status()
            payload = _BlsResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise BlsProviderError("BLS CPI data is unavailable") from exc
        if payload.status != "REQUEST_SUCCEEDED":
            detail = "; ".join(payload.message) or "request failed"
            raise BlsProviderError(f"BLS CPI request failed: {detail}")
        if payload.Results is None or len(payload.Results.series) != 1:
            raise BlsProviderError("BLS CPI response did not contain one series")
        series = payload.Results.series[0]
        if series.seriesID != CPI_SERIES_ID or not series.data:
            raise BlsProviderError("BLS CPI response did not contain the requested series")
        point = series.data[0]
        try:
            value = Decimal(point.value)
        except InvalidOperation as exc:
            raise BlsProviderError("BLS CPI value was not numeric") from exc
        return MacroObservation(
            series_id=series.seriesID,
            reference_period=f"{point.year}-{point.period[1:]}",
            value=value,
            source_url=CPI_SOURCE_URL,
            retrieved_at=self.clock().astimezone(UTC),
        )

    async def cpi_releases(self) -> tuple[MacroRelease, ...]:
        try:
            response = await self.http.get(self.calendar_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BlsProviderError("BLS release calendar is unavailable") from exc
        retrieved_at = self.clock().astimezone(UTC)
        releases = []
        for event in _calendar_events(response.text):
            title = event.get("SUMMARY", "")
            if "consumer price index" not in title.casefold():
                continue
            raw_start = event.get("DTSTART")
            if raw_start is None:
                continue
            releases.append(
                MacroRelease(
                    external_id=event.get("UID", f"bls-cpi-{raw_start}"),
                    title=title,
                    scheduled_at=_parse_calendar_datetime(
                        raw_start,
                        event.get("DTSTART_TZID"),
                    ),
                    source_url=CPI_CALENDAR_SOURCE_URL,
                    retrieved_at=retrieved_at,
                )
            )
        return tuple(sorted(releases, key=lambda item: item.scheduled_at))


def _calendar_events(payload: str) -> tuple[dict[str, str], ...]:
    unfolded = payload.replace("\r\n ", "").replace("\n ", "")
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in unfolded.splitlines():
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        raw_key, value = line.split(":", 1)
        key, *parameters = raw_key.split(";")
        current[key] = value.replace("\\,", ",").replace("\\n", " ")
        for parameter in parameters:
            if parameter.startswith("TZID="):
                current[f"{key}_TZID"] = parameter.removeprefix("TZID=")
    return tuple(events)


def _parse_calendar_datetime(value: str, timezone_name: str | None) -> datetime:
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    try:
        resolved_timezone = (
            "America/New_York"
            if timezone_name in {None, "Eastern Standard Time", "US-Eastern"}
            else timezone_name
        )
        timezone = ZoneInfo(resolved_timezone)
    except ZoneInfoNotFoundError as exc:
        raise BlsProviderError("BLS calendar used an unknown timezone") from exc
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=timezone).astimezone(UTC)
