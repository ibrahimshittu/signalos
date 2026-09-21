from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MacroObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["bls"] = "bls"
    indicator: Literal["consumer_price_index"] = "consumer_price_index"
    series_id: str
    reference_period: str = Field(pattern=r"^\d{4}-\d{2}$")
    value: Decimal
    unit: Literal["index_1982_1984_100"] = "index_1982_1984_100"
    source_url: str
    retrieved_at: datetime


class MacroRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["bls"] = "bls"
    indicator: Literal["consumer_price_index"] = "consumer_price_index"
    external_id: str
    title: str
    scheduled_at: datetime
    source_url: str
    retrieved_at: datetime
