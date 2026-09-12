from __future__ import annotations

from collections.abc import Sequence

import httpx
from pydantic import TypeAdapter, ValidationError

from signalos_backend.notifications.domain import (
    ExpoPushMessage,
    ExpoPushReceipt,
    ExpoPushTicket,
)

_TICKETS = TypeAdapter(list[ExpoPushTicket])
_RECEIPTS = TypeAdapter(dict[str, ExpoPushReceipt])


class ExpoPushError(RuntimeError):
    pass


class ExpoPushGateway:
    def __init__(
        self,
        *,
        access_token: str,
        base_url: str = "https://exp.host/--/api/v2/push",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=10.0)
        self.headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def send(self, messages: Sequence[ExpoPushMessage]) -> tuple[ExpoPushTicket, ...]:
        if not messages:
            return ()
        if len(messages) > 100:
            raise ValueError("Expo accepts at most 100 push messages per request")
        try:
            response = await self.client.post(
                f"{self.base_url}/send",
                headers=self.headers,
                json=[message.model_dump(mode="json") for message in messages],
            )
            response.raise_for_status()
            payload = response.json()
            tickets = _TICKETS.validate_python(payload["data"])
        except (httpx.HTTPError, KeyError, ValueError, ValidationError) as exc:
            raise ExpoPushError("Expo push request failed") from exc
        if len(tickets) != len(messages):
            raise ExpoPushError("Expo returned a mismatched push ticket count")
        return tuple(tickets)

    async def receipts(self, ticket_ids: Sequence[str]) -> dict[str, ExpoPushReceipt]:
        if not ticket_ids:
            return {}
        if len(ticket_ids) > 1_000:
            raise ValueError("Expo accepts at most 1000 receipt IDs per request")
        try:
            response = await self.client.post(
                f"{self.base_url}/getReceipts",
                headers=self.headers,
                json={"ids": list(ticket_ids)},
            )
            response.raise_for_status()
            payload = response.json()
            return _RECEIPTS.validate_python(payload["data"])
        except (httpx.HTTPError, KeyError, ValueError, ValidationError) as exc:
            raise ExpoPushError("Expo receipt request failed") from exc
