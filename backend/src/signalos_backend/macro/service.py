from __future__ import annotations

from signalos_backend.macro.bls import BlsClient
from signalos_backend.macro.domain import MacroObservation, MacroRelease


class MacroService:
    def __init__(self, bls: BlsClient) -> None:
        self.bls = bls

    async def latest_cpi(self) -> MacroObservation:
        return await self.bls.latest_cpi()

    async def cpi_releases(self) -> tuple[MacroRelease, ...]:
        return await self.bls.cpi_releases()
