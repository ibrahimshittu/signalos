from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SessionName(StrEnum):
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"
    UTC_ROLLOVER = "utc_rollover"
    FUNDING = "funding"


class SweepOffset(StrEnum):
    PRE_OPEN = "t_minus_15"
    OPEN = "t0"
    POST_15 = "t_plus_15"
    POST_60 = "t_plus_60"


_OFFSETS = (
    (SweepOffset.PRE_OPEN, timedelta(minutes=-15)),
    (SweepOffset.OPEN, timedelta(0)),
    (SweepOffset.POST_15, timedelta(minutes=15)),
    (SweepOffset.POST_60, timedelta(minutes=60)),
)


class SessionSweep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session: SessionName
    offset: SweepOffset
    scheduled_at: datetime
    anchor_at: datetime
    symbol: str | None = Field(default=None, pattern=r"^[A-Z0-9-]{4,40}$")

    @model_validator(mode="after")
    def timestamps_are_aware(self) -> SessionSweep:
        if self.scheduled_at.tzinfo is None or self.anchor_at.tzinfo is None:
            raise ValueError("session timestamps must be timezone-aware")
        return self


@dataclass(frozen=True)
class _SessionDefinition:
    timezone: ZoneInfo
    local_time: time


_SESSIONS = {
    SessionName.TOKYO: _SessionDefinition(ZoneInfo("Asia/Tokyo"), time(9, 0)),
    SessionName.LONDON: _SessionDefinition(ZoneInfo("Europe/London"), time(8, 0)),
    SessionName.NEW_YORK: _SessionDefinition(ZoneInfo("America/New_York"), time(9, 30)),
    SessionName.UTC_ROLLOVER: _SessionDefinition(ZoneInfo("UTC"), time(0, 0)),
}


class SessionScheduler:
    """Create DST-aware analysis windows; a window never implies a trade."""

    def __init__(
        self,
        *,
        closed_dates: dict[SessionName, frozenset[date]] | None = None,
    ) -> None:
        self.closed_dates = closed_dates or {}

    def sweeps_for_date(self, session: SessionName, local_date: date) -> tuple[SessionSweep, ...]:
        if session is SessionName.FUNDING:
            raise ValueError("funding sweeps require an instrument event time")
        if local_date in self.closed_dates.get(session, frozenset()):
            return ()
        definition = _SESSIONS[session]
        anchor = datetime.combine(
            local_date, definition.local_time, tzinfo=definition.timezone
        ).astimezone(UTC)
        return tuple(
            SessionSweep(
                session=session,
                offset=offset,
                scheduled_at=anchor + delta,
                anchor_at=anchor,
            )
            for offset, delta in _OFFSETS
        )

    def funding_sweeps(self, symbol: str, funding_time: datetime) -> tuple[SessionSweep, ...]:
        if funding_time.tzinfo is None:
            raise ValueError("funding_time must be timezone-aware")
        anchor = funding_time.astimezone(UTC)
        return tuple(
            SessionSweep(
                session=SessionName.FUNDING,
                offset=offset,
                scheduled_at=anchor + delta,
                anchor_at=anchor,
                symbol=symbol.upper(),
            )
            for offset, delta in _OFFSETS
        )

    def due_sweeps(self, at: datetime, *, tolerance_seconds: int = 30) -> tuple[SessionSweep, ...]:
        """Return scheduled global activity windows close enough for this worker tick."""

        if at.tzinfo is None:
            raise ValueError("at must be timezone-aware")
        if not 0 <= tolerance_seconds <= 300:
            raise ValueError("tolerance_seconds must be between 0 and 300")
        now = at.astimezone(UTC)
        tolerance = timedelta(seconds=tolerance_seconds)
        due: list[SessionSweep] = []
        for session, definition in _SESSIONS.items():
            local_date = now.astimezone(definition.timezone).date()
            for day_offset in (-1, 0, 1):
                for sweep in self.sweeps_for_date(session, local_date + timedelta(days=day_offset)):
                    if abs(sweep.scheduled_at - now) <= tolerance:
                        due.append(sweep)
        return tuple(sorted(due, key=lambda item: (item.scheduled_at, item.session.value)))
