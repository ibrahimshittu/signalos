from __future__ import annotations

import hashlib
import json

from signalos_backend.execution.domain import BrokerPosition


def position_portfolio_fingerprint(positions: tuple[BrokerPosition, ...]) -> str:
    """Hash only risk-bearing position terms, excluding prices and floating PnL."""

    payload = [
        {
            "average_price": str(position.average_price),
            "category": position.category.value,
            "leverage": str(position.leverage) if position.leverage is not None else None,
            "position_index": position.position_index,
            "side": position.side.value,
            "size": str(position.size),
            "stop_loss": str(position.stop_loss) if position.stop_loss is not None else None,
            "symbol": position.symbol,
            "take_profit": (
                str(position.take_profit) if position.take_profit is not None else None
            ),
        }
        for position in sorted(
            positions,
            key=lambda item: (item.category.value, item.symbol, item.position_index),
        )
    ]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
