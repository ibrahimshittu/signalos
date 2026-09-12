from __future__ import annotations

import hashlib
import hmac
import json
import time
from asyncio import gather
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from signalos_backend.brokers.domain import (
    AccountBalance,
    AccountSnapshot,
    BrokerCredentialRejected,
    BrokerEnvironment,
    BrokerOrderRejected,
    BrokerProviderError,
    BybitKeyInfo,
)
from signalos_backend.execution.domain import (
    BrokerExecutionSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderSnapshot,
    BrokerPositionSnapshot,
)
from signalos_backend.market.domain import Candle, Instrument, MarketCategory, TickerSnapshot
from signalos_backend.proposals.domain import OrderSide, OrderType


class _BybitEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    ret_code: int = Field(alias="retCode")
    ret_msg: str = Field(alias="retMsg")
    result: dict[str, Any]
    time: int


class _BybitKeyInfoResult(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    user_id: int | str = Field(alias="userID")
    parent_uid: int | str = Field(default="0", alias="parentUid")
    is_master: bool = Field(alias="isMaster")
    read_only: int = Field(alias="readOnly")
    ips: list[str] = Field(default_factory=list)
    permissions: dict[str, list[str]] = Field(default_factory=dict)


class _BybitCoin(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    coin: str
    wallet_balance: str = Field(alias="walletBalance")
    equity: str
    available_to_withdraw: str = Field(default="0", alias="availableToWithdraw")


class _BybitWallet(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    account_type: str = Field(alias="accountType")
    total_equity: str = Field(alias="totalEquity")
    total_available_balance: str = Field(alias="totalAvailableBalance")
    coin: list[_BybitCoin] = Field(default_factory=list)


class _BybitPriceFilter(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    tick_size: str = Field(alias="tickSize")


class _BybitLotSizeFilter(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    quantity_step: str | None = Field(default=None, alias="qtyStep")
    base_precision: str | None = Field(default=None, alias="basePrecision")
    minimum_order_quantity: str | None = Field(default=None, alias="minOrderQty")
    minimum_notional: str | None = Field(default=None, alias="minNotionalValue")
    minimum_order_amount: str | None = Field(default=None, alias="minOrderAmt")


class _BybitInstrument(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    symbol: str
    status: str
    base_coin: str = Field(alias="baseCoin")
    quote_coin: str = Field(alias="quoteCoin")
    settle_coin: str | None = Field(default=None, alias="settleCoin")
    contract_type: str | None = Field(default=None, alias="contractType")
    funding_interval: int | None = Field(default=None, alias="fundingInterval")
    price_filter: _BybitPriceFilter = Field(alias="priceFilter")
    lot_size_filter: _BybitLotSizeFilter = Field(alias="lotSizeFilter")


class _BybitTicker(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    symbol: str
    last_price: str = Field(alias="lastPrice")
    bid_price: str = Field(alias="bid1Price")
    ask_price: str = Field(alias="ask1Price")
    turnover_24h: str = Field(alias="turnover24h")
    volume_24h: str = Field(alias="volume24h")
    price_change_24h: str = Field(alias="price24hPcnt")
    open_interest: str | None = Field(default=None, alias="openInterest")
    funding_rate: str | None = Field(default=None, alias="fundingRate")
    next_funding_time: str | None = Field(default=None, alias="nextFundingTime")


class _BybitRiskLimit(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    symbol: str
    is_lowest_risk: int = Field(alias="isLowestRisk")
    max_leverage: str = Field(alias="maxLeverage")


class _BybitOrder(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    order_id: str = Field(alias="orderId")
    order_link_id: str = Field(default="", alias="orderLinkId")
    category: str
    symbol: str
    side: str
    order_type: str = Field(alias="orderType")
    order_status: str = Field(alias="orderStatus")
    quantity: str = Field(alias="qty")
    cumulative_executed_quantity: str = Field(alias="cumExecQty")
    leaves_quantity: str = Field(alias="leavesQty")
    average_price: str = Field(default="", alias="avgPrice")
    updated_time: str = Field(alias="updatedTime")


class _BybitExecution(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    execution_id: str = Field(alias="execId")
    order_id: str = Field(alias="orderId")
    order_link_id: str = Field(default="", alias="orderLinkId")
    symbol: str
    side: str
    price: str = Field(alias="execPrice")
    quantity: str = Field(alias="execQty")
    value: str = Field(alias="execValue")
    fee: str = Field(alias="execFee")
    executed_time: str = Field(alias="execTime")


class _BybitPosition(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    position_index: int = Field(alias="positionIdx")
    symbol: str
    side: str
    size: str
    average_price: str = Field(alias="avgPrice")
    position_value: str = Field(alias="positionValue")
    leverage: str
    mark_price: str = Field(alias="markPrice")
    liquidation_price: str = Field(default="", alias="liqPrice")
    take_profit: str = Field(default="", alias="takeProfit")
    stop_loss: str = Field(default="", alias="stopLoss")
    unrealised_pnl: str = Field(alias="unrealisedPnl")
    cumulative_realised_pnl: str = Field(alias="cumRealisedPnl")
    sequence: int = Field(alias="seq")
    updated_time: str = Field(alias="updatedTime")


def sign_get_request(
    *, timestamp_ms: int, api_key: str, api_secret: str, recv_window_ms: int, query: str
) -> str:
    """Build Bybit's HMAC-SHA256 signature for an authenticated GET request.

    Source: https://bybit-exchange.github.io/docs/v5/guide#create-a-request
    """

    plaintext = f"{timestamp_ms}{api_key}{recv_window_ms}{query}"
    return hmac.new(api_secret.encode(), plaintext.encode(), hashlib.sha256).hexdigest()


def sign_post_request(
    *, timestamp_ms: int, api_key: str, api_secret: str, recv_window_ms: int, body: str
) -> str:
    """Build Bybit's HMAC-SHA256 signature for the exact JSON body sent."""

    plaintext = f"{timestamp_ms}{api_key}{recv_window_ms}{body}"
    return hmac.new(api_secret.encode(), plaintext.encode(), hashlib.sha256).hexdigest()


class BybitHttpGateway:
    """Small typed Bybit V5 adapter; untrusted payloads are validated before use."""

    def __init__(
        self,
        *,
        mainnet_base_url: str,
        testnet_base_url: str,
        recv_window_ms: int = 5_000,
        timeout_seconds: float = 10,
        client: httpx.AsyncClient | None = None,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self.mainnet_base_url = mainnet_base_url.rstrip("/")
        self.testnet_base_url = testnet_base_url.rstrip("/")
        self.recv_window_ms = recv_window_ms
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds), follow_redirects=False
        )
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_key_info(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
    ) -> BybitKeyInfo:
        payload = await self._signed_get(
            path="/v5/user/query-api",
            params={},
            api_key=api_key,
            api_secret=api_secret,
            environment=environment,
        )
        try:
            result = _BybitKeyInfoResult.model_validate(payload)
        except ValidationError as exc:
            raise BrokerProviderError("Bybit returned invalid API key metadata") from exc
        return BybitKeyInfo(
            user_id=str(result.user_id),
            parent_uid=str(result.parent_uid),
            is_master=result.is_master,
            read_only=result.read_only == 1,
            ips=tuple(result.ips),
            permissions={key: tuple(value) for key, value in result.permissions.items()},
        )

    async def get_instruments(self, *, environment: BrokerEnvironment) -> tuple[Instrument, ...]:
        """Fetch every active USDT spot and linear instrument.

        Linear instruments are cursor-paginated because Bybit documents more than 500 symbols.
        Source: https://bybit-exchange.github.io/docs/v5/market/instrument
        """

        instruments: list[Instrument] = []
        spot = await self._public_get(
            path="/v5/market/instruments-info",
            params={"category": "spot"},
            environment=environment,
        )
        instruments.extend(self._parse_instruments(spot, MarketCategory.SPOT))

        cursor: str | None = None
        while True:
            params = {"category": "linear", "limit": "1000"}
            if cursor:
                params["cursor"] = cursor
            page = await self._public_get(
                path="/v5/market/instruments-info",
                params=params,
                environment=environment,
            )
            instruments.extend(self._parse_instruments(page, MarketCategory.LINEAR))
            next_cursor = page.get("nextPageCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                break
            cursor = next_cursor
        return tuple(instruments)

    async def get_account_snapshot(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
    ) -> AccountSnapshot:
        payload = await self._signed_get(
            path="/v5/account/wallet-balance",
            params={"accountType": "UNIFIED"},
            api_key=api_key,
            api_secret=api_secret,
            environment=environment,
        )
        wallets = payload.get("list")
        if not isinstance(wallets, list) or not wallets:
            raise BrokerProviderError("Bybit returned no unified wallet account")
        try:
            wallet = _BybitWallet.model_validate(wallets[0])
            balances = tuple(
                AccountBalance(
                    coin=coin.coin.upper(),
                    wallet_balance=_decimal(coin.wallet_balance),
                    equity=_decimal(coin.equity),
                    available_to_withdraw=_decimal(coin.available_to_withdraw or "0"),
                )
                for coin in wallet.coin
            )
            return AccountSnapshot(
                account_type=wallet.account_type,
                total_equity=_decimal(wallet.total_equity),
                available_balance=_decimal(wallet.total_available_balance),
                balances=balances,
            )
        except (ValidationError, InvalidOperation) as exc:
            raise BrokerProviderError("Bybit returned invalid wallet balance data") from exc

    async def get_tickers(self, *, environment: BrokerEnvironment) -> tuple[TickerSnapshot, ...]:
        """Fetch broad spot and linear ticker snapshots from Bybit V5."""

        spot, linear = await gather(
            self._public_envelope(
                path="/v5/market/tickers",
                params={"category": "spot"},
                environment=environment,
            ),
            self._public_envelope(
                path="/v5/market/tickers",
                params={"category": "linear"},
                environment=environment,
            ),
        )
        return (
            *self._parse_tickers(spot, MarketCategory.SPOT),
            *self._parse_tickers(linear, MarketCategory.LINEAR),
        )

    async def get_ticker_snapshot(
        self,
        *,
        environment: BrokerEnvironment,
        category: MarketCategory,
        symbol: str,
    ) -> TickerSnapshot:
        envelope = await self._public_envelope(
            path="/v5/market/tickers",
            params={"category": category.value, "symbol": symbol},
            environment=environment,
        )
        values = self._parse_tickers(envelope, category)
        try:
            return next(value for value in values if value.symbol == symbol)
        except StopIteration as exc:
            raise BrokerProviderError("Bybit returned no ticker for the requested symbol") from exc

    async def get_max_leverage(
        self,
        *,
        environment: BrokerEnvironment,
        category: MarketCategory,
        symbol: str,
    ) -> Decimal:
        """Return the current lowest-risk-tier leverage ceiling for a symbol.

        Source: https://bybit-exchange.github.io/docs/v5/market/risk-limit
        """

        if category is MarketCategory.SPOT:
            return Decimal("1")
        payload = await self._public_get(
            path="/v5/market/risk-limit",
            params={"category": category.value, "symbol": symbol},
            environment=environment,
        )
        values = payload.get("list")
        if not isinstance(values, list):
            raise BrokerProviderError("Bybit returned invalid risk-limit data")
        try:
            tiers = tuple(_BybitRiskLimit.model_validate(value) for value in values)
            lowest = next(
                tier for tier in tiers if tier.symbol == symbol and tier.is_lowest_risk == 1
            )
            maximum = _decimal(lowest.max_leverage)
        except (ValidationError, InvalidOperation, StopIteration) as exc:
            raise BrokerProviderError("Bybit returned invalid risk-limit data") from exc
        if maximum < 1:
            raise BrokerProviderError("Bybit returned invalid risk-limit leverage")
        return maximum

    async def get_closed_klines(
        self,
        *,
        environment: BrokerEnvironment,
        category: MarketCategory,
        symbol: str,
        interval_minutes: int = 15,
        limit: int = 200,
    ) -> tuple[Candle, ...]:
        """Return chronological, completed REST candles and discard the live candle.

        Bybit documents that the current candle's close is only the last traded price.
        Source: https://bybit-exchange.github.io/docs/v5/market/kline
        """

        if interval_minutes not in {1, 3, 5, 15, 30, 60, 120, 240, 360, 720}:
            raise ValueError("unsupported Bybit kline interval")
        if not 1 <= limit <= 1_000:
            raise ValueError("Bybit kline limit must be between 1 and 1000")
        envelope = await self._public_envelope(
            path="/v5/market/kline",
            params={
                "category": category.value,
                "interval": str(interval_minutes),
                "limit": str(limit),
                "symbol": symbol,
            },
            environment=environment,
        )
        values = envelope.result.get("list")
        if not isinstance(values, list):
            raise BrokerProviderError("Bybit returned invalid kline data")
        interval_ms = interval_minutes * 60_000
        parsed: list[Candle] = []
        try:
            for raw in values:
                if not isinstance(raw, list) or len(raw) < 7:
                    raise ValueError("invalid kline row")
                start_ms = int(raw[0])
                if start_ms + interval_ms > envelope.time:
                    continue
                parsed.append(
                    Candle(
                        category=category,
                        symbol=symbol,
                        interval_minutes=interval_minutes,
                        start_at=_millisecond_time(start_ms),
                        end_at=_millisecond_time(start_ms + interval_ms),
                        open_price=_decimal(raw[1]),
                        high_price=_decimal(raw[2]),
                        low_price=_decimal(raw[3]),
                        close_price=_decimal(raw[4]),
                        volume=_decimal(raw[5]),
                        turnover=_decimal(raw[6]),
                    )
                )
        except (ValidationError, InvalidOperation, TypeError, ValueError, OSError) as exc:
            raise BrokerProviderError("Bybit returned invalid kline data") from exc
        return tuple(sorted(parsed, key=lambda candle: candle.start_at))

    async def set_leverage(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
        category: str,
        symbol: str,
        leverage: str,
    ) -> None:
        await self._signed_post(
            path="/v5/position/set-leverage",
            payload={
                "buyLeverage": leverage,
                "category": category,
                "sellLeverage": leverage,
                "symbol": symbol,
            },
            api_key=api_key,
            api_secret=api_secret,
            environment=environment,
            accepted_ret_codes=frozenset({0, 110043}),
        )

    async def place_order(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
        category: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: str | None,
        stop_loss: str,
        take_profit: str,
        order_link_id: str,
    ) -> BrokerOrderAcknowledgement:
        payload = {
            "category": category,
            "orderLinkId": order_link_id,
            "orderType": order_type,
            "qty": quantity,
            "side": side,
            "stopLoss": stop_loss,
            "symbol": symbol,
            "takeProfit": take_profit,
        }
        if price is not None:
            payload["price"] = price
            payload["timeInForce"] = "GTC"
        result = await self._signed_post(
            path="/v5/order/create",
            payload=payload,
            api_key=api_key,
            api_secret=api_secret,
            environment=environment,
        )
        try:
            return BrokerOrderAcknowledgement(
                order_id=result["orderId"],
                order_link_id=result["orderLinkId"],
            )
        except (KeyError, ValidationError) as exc:
            raise BrokerProviderError("Bybit returned an invalid order acknowledgement") from exc

    async def get_order_snapshot(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
        category: str,
        order_link_id: str,
    ) -> BrokerOrderSnapshot | None:
        """Read the broker's current state for a SignalOS-linked order."""

        result = await self._signed_get(
            path="/v5/order/realtime",
            params={"category": category, "orderLinkId": order_link_id},
            api_key=api_key,
            api_secret=api_secret,
            environment=environment,
        )
        values = result.get("list")
        if not isinstance(values, list):
            raise BrokerProviderError("Bybit returned invalid order state data")
        if not values:
            result = await self._signed_get(
                path="/v5/order/history",
                params={"category": category, "orderLinkId": order_link_id, "limit": "1"},
                api_key=api_key,
                api_secret=api_secret,
                environment=environment,
            )
            values = result.get("list")
            if not isinstance(values, list):
                raise BrokerProviderError("Bybit returned invalid historical order data")
            if not values:
                return None
        try:
            item = _BybitOrder.model_validate(values[0])
            return BrokerOrderSnapshot(
                order_id=item.order_id,
                order_link_id=item.order_link_id,
                category=MarketCategory(item.category),
                symbol=item.symbol,
                side=_order_side(item.side),
                order_type=OrderType(item.order_type.lower()),
                status=item.order_status,
                quantity=_decimal(item.quantity),
                cumulative_executed_quantity=_decimal(item.cumulative_executed_quantity),
                leaves_quantity=_decimal(item.leaves_quantity),
                average_price=_optional_decimal(item.average_price),
                updated_at=_millisecond_time(int(item.updated_time)),
            )
        except (ValidationError, InvalidOperation, ValueError, OSError) as exc:
            raise BrokerProviderError("Bybit returned invalid order state data") from exc

    async def get_executions(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
        category: str,
        start_time_ms: int,
    ) -> tuple[BrokerExecutionSnapshot, ...]:
        """Return execution fills, following Bybit's cursor pagination."""

        values: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params = {
                "category": category,
                "limit": "100",
                "startTime": str(start_time_ms),
            }
            if cursor:
                params["cursor"] = cursor
            result = await self._signed_get(
                path="/v5/execution/list",
                params=params,
                api_key=api_key,
                api_secret=api_secret,
                environment=environment,
            )
            page = result.get("list")
            if not isinstance(page, list):
                raise BrokerProviderError("Bybit returned invalid execution data")
            values.extend(page)
            next_cursor = result.get("nextPageCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                break
            cursor = next_cursor
        try:
            return tuple(
                BrokerExecutionSnapshot(
                    execution_id=(item := _BybitExecution.model_validate(raw)).execution_id,
                    order_id=item.order_id,
                    order_link_id=item.order_link_id,
                    symbol=item.symbol,
                    side=_order_side(item.side),
                    price=_decimal(item.price),
                    quantity=_decimal(item.quantity),
                    value=_decimal(item.value),
                    fee=_decimal(item.fee),
                    executed_at=_millisecond_time(int(item.executed_time)),
                )
                for raw in values
            )
        except (ValidationError, InvalidOperation, ValueError, OSError) as exc:
            raise BrokerProviderError("Bybit returned invalid execution data") from exc

    async def get_positions(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
        category: str,
        settle_coin: str,
    ) -> tuple[BrokerPositionSnapshot, ...]:
        """Return every non-zero USDT derivatives position for an account."""

        values: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params = {"category": category, "limit": "200", "settleCoin": settle_coin}
            if cursor:
                params["cursor"] = cursor
            result = await self._signed_get(
                path="/v5/position/list",
                params=params,
                api_key=api_key,
                api_secret=api_secret,
                environment=environment,
            )
            page = result.get("list")
            if not isinstance(page, list):
                raise BrokerProviderError("Bybit returned invalid position data")
            values.extend(page)
            next_cursor = result.get("nextPageCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                break
            cursor = next_cursor
        try:
            positions: list[BrokerPositionSnapshot] = []
            for raw in values:
                item = _BybitPosition.model_validate(raw)
                size = _decimal(item.size)
                if size <= 0 or item.side not in {"Buy", "Sell"}:
                    continue
                positions.append(
                    BrokerPositionSnapshot(
                        category=MarketCategory(category),
                        symbol=item.symbol,
                        position_index=item.position_index,
                        side=_order_side(item.side),
                        size=size,
                        average_price=_decimal(item.average_price),
                        position_value=_decimal(item.position_value),
                        leverage=_optional_decimal(item.leverage),
                        mark_price=_decimal(item.mark_price),
                        liquidation_price=_optional_decimal(item.liquidation_price),
                        take_profit=_optional_decimal(item.take_profit),
                        stop_loss=_optional_decimal(item.stop_loss),
                        unrealised_pnl=_decimal(item.unrealised_pnl),
                        cumulative_realised_pnl=_decimal(item.cumulative_realised_pnl),
                        sequence=item.sequence,
                        updated_at=_millisecond_time(int(item.updated_time)),
                    )
                )
            return tuple(positions)
        except (ValidationError, InvalidOperation, ValueError, OSError) as exc:
            raise BrokerProviderError("Bybit returned invalid position data") from exc

    async def cancel_order(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
        category: str,
        symbol: str,
        order_id: str,
        order_link_id: str,
    ) -> BrokerOrderAcknowledgement:
        result = await self._signed_post(
            path="/v5/order/cancel",
            payload={
                "category": category,
                "orderId": order_id,
                "orderLinkId": order_link_id,
                "symbol": symbol,
            },
            api_key=api_key,
            api_secret=api_secret,
            environment=environment,
        )
        return _order_acknowledgement(result)

    async def close_position(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
        category: str,
        symbol: str,
        position_index: int,
        open_side: str,
        quantity: str,
        order_link_id: str,
    ) -> BrokerOrderAcknowledgement:
        result = await self._signed_post(
            path="/v5/order/create",
            payload={
                "category": category,
                "orderLinkId": order_link_id,
                "orderType": "Market",
                "positionIdx": position_index,
                "qty": quantity,
                "reduceOnly": True,
                "side": "Sell" if open_side == "Buy" else "Buy",
                "symbol": symbol,
            },
            api_key=api_key,
            api_secret=api_secret,
            environment=environment,
        )
        return _order_acknowledgement(result)

    async def set_trading_stop(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
        category: str,
        symbol: str,
        position_index: int,
        stop_loss: str,
        take_profit: str,
    ) -> None:
        await self._signed_post(
            path="/v5/position/trading-stop",
            payload={
                "category": category,
                "positionIdx": position_index,
                "stopLoss": stop_loss,
                "symbol": symbol,
                "takeProfit": take_profit,
                "tpslMode": "Full",
            },
            api_key=api_key,
            api_secret=api_secret,
            environment=environment,
        )

    async def _signed_get(
        self,
        *,
        path: str,
        params: Mapping[str, str],
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
    ) -> dict[str, Any]:
        query = urlencode(sorted(params.items()))
        timestamp_ms = self._clock_ms()
        signature = sign_get_request(
            timestamp_ms=timestamp_ms,
            api_key=api_key,
            api_secret=api_secret,
            recv_window_ms=self.recv_window_ms,
            query=query,
        )
        base_url = self._base_url(environment)
        url = f"{base_url}{path}" + (f"?{query}" if query else "")
        headers = {
            "X-BAPI-API-KEY": api_key,
            "X-BAPI-TIMESTAMP": str(timestamp_ms),
            "X-BAPI-RECV-WINDOW": str(self.recv_window_ms),
            "X-BAPI-SIGN": signature,
        }
        try:
            response = await self._client.get(url, headers=headers)
            response.raise_for_status()
            envelope = _BybitEnvelope.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise BrokerProviderError("Bybit request failed") from exc
        if envelope.ret_code != 0:
            message = envelope.ret_msg[:160] or "unknown error"
            if envelope.ret_code == 10003:
                account_label = (
                    "Live account"
                    if environment is BrokerEnvironment.MAINNET
                    else "Test account"
                )
                key_source = (
                    "your live Bybit account"
                    if environment is BrokerEnvironment.MAINNET
                    else "Bybit Testnet"
                )
                raise BrokerCredentialRejected(
                    envelope.ret_code,
                    f"Bybit does not recognize this API key for the selected {account_label}. "
                    f"Create the key in {key_source} and copy the matching secret. "
                    "Demo Trading keys are not supported.",
                )
            if envelope.ret_code in {10004, 10005, 10007, 10010, -2015, 33004}:
                raise BrokerCredentialRejected(
                    envelope.ret_code,
                    f"Bybit rejected these API credentials ({envelope.ret_code}): {message}",
                )
            raise BrokerProviderError(f"Bybit rejected request ({envelope.ret_code}): {message}")
        return envelope.result

    async def _signed_post(
        self,
        *,
        path: str,
        payload: Mapping[str, Any],
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
        accepted_ret_codes: frozenset[int] = frozenset({0}),
    ) -> dict[str, Any]:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        timestamp_ms = self._clock_ms()
        signature = sign_post_request(
            timestamp_ms=timestamp_ms,
            api_key=api_key,
            api_secret=api_secret,
            recv_window_ms=self.recv_window_ms,
            body=body,
        )
        headers = {
            "Content-Type": "application/json",
            "X-BAPI-API-KEY": api_key,
            "X-BAPI-RECV-WINDOW": str(self.recv_window_ms),
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": str(timestamp_ms),
        }
        try:
            response = await self._client.post(
                f"{self._base_url(environment)}{path}",
                content=body,
                headers=headers,
            )
            response.raise_for_status()
            envelope = _BybitEnvelope.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise BrokerProviderError("Bybit authenticated request failed") from exc
        if envelope.ret_code not in accepted_ret_codes:
            message = envelope.ret_msg[:160] or "unknown error"
            raise BrokerOrderRejected(
                envelope.ret_code,
                f"Bybit rejected order request ({envelope.ret_code}): {message}",
            )
        return envelope.result

    async def _public_get(
        self,
        *,
        path: str,
        params: Mapping[str, str],
        environment: BrokerEnvironment,
    ) -> dict[str, Any]:
        return (
            await self._public_envelope(path=path, params=params, environment=environment)
        ).result

    async def _public_envelope(
        self,
        *,
        path: str,
        params: Mapping[str, str],
        environment: BrokerEnvironment,
    ) -> _BybitEnvelope:
        try:
            response = await self._client.get(f"{self._base_url(environment)}{path}", params=params)
            response.raise_for_status()
            envelope = _BybitEnvelope.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise BrokerProviderError("Bybit public market request failed") from exc
        if envelope.ret_code != 0:
            message = envelope.ret_msg[:160] or "unknown error"
            raise BrokerProviderError(
                f"Bybit rejected public market request ({envelope.ret_code}): {message}"
            )
        return envelope

    def _parse_instruments(
        self, payload: dict[str, Any], category: MarketCategory
    ) -> tuple[Instrument, ...]:
        values = payload.get("list")
        if not isinstance(values, list):
            raise BrokerProviderError("Bybit returned invalid instrument data")
        parsed: list[Instrument] = []
        try:
            for raw in values:
                item = _BybitInstrument.model_validate(raw)
                if item.status != "Trading" or item.quote_coin != "USDT":
                    continue
                if category is MarketCategory.LINEAR and (
                    item.settle_coin != "USDT"
                    or item.contract_type not in {"LinearPerpetual", "LinearFutures"}
                ):
                    continue
                minimum_notional = (
                    item.lot_size_filter.minimum_notional
                    or item.lot_size_filter.minimum_order_amount
                    or "0"
                )
                # Bybit uses `qtyStep` for derivatives and `basePrecision` for
                # spot. Their public response is category-specific even though
                # both products share this endpoint.
                quantity_step = (
                    item.lot_size_filter.quantity_step
                    or item.lot_size_filter.base_precision
                )
                if quantity_step is None:
                    raise ValueError("instrument quantity precision is missing")
                minimum_order_quantity = (
                    item.lot_size_filter.minimum_order_quantity or quantity_step
                )
                funding_interval = (
                    item.funding_interval
                    if category is MarketCategory.LINEAR
                    and item.funding_interval is not None
                    and item.funding_interval > 0
                    else None
                )
                parsed.append(
                    Instrument(
                        category=category,
                        symbol=item.symbol,
                        base_coin=item.base_coin,
                        quote_coin=item.quote_coin,
                        status=item.status,
                        tick_size=_decimal(item.price_filter.tick_size),
                        quantity_step=_decimal(quantity_step),
                        minimum_order_quantity=_decimal(minimum_order_quantity),
                        minimum_notional=_decimal(minimum_notional),
                        funding_interval_minutes=funding_interval,
                    )
                )
        except (ValidationError, InvalidOperation, ValueError) as exc:
            raise BrokerProviderError("Bybit returned invalid instrument data") from exc
        return tuple(parsed)

    @staticmethod
    def _parse_tickers(
        envelope: _BybitEnvelope, category: MarketCategory
    ) -> tuple[TickerSnapshot, ...]:
        values = envelope.result.get("list")
        if not isinstance(values, list):
            raise BrokerProviderError("Bybit returned invalid ticker data")
        try:
            observed_at = _millisecond_time(envelope.time)
            return tuple(
                TickerSnapshot(
                    category=category,
                    symbol=(item := _BybitTicker.model_validate(raw)).symbol,
                    last_price=_decimal(item.last_price),
                    bid_price=_decimal(item.bid_price),
                    ask_price=_decimal(item.ask_price),
                    turnover_24h=_decimal(item.turnover_24h),
                    volume_24h=_decimal(item.volume_24h),
                    price_change_24h=_decimal(item.price_change_24h),
                    open_interest=_optional_decimal(item.open_interest),
                    funding_rate=_optional_decimal(item.funding_rate),
                    next_funding_at=(
                        _millisecond_time(int(item.next_funding_time))
                        if item.next_funding_time
                        else None
                    ),
                    observed_at=observed_at,
                )
                for raw in values
            )
        except (ValidationError, InvalidOperation, ValueError, OSError) as exc:
            raise BrokerProviderError("Bybit returned invalid ticker data") from exc

    def _base_url(self, environment: BrokerEnvironment) -> str:
        return (
            self.mainnet_base_url
            if environment is BrokerEnvironment.MAINNET
            else self.testnet_base_url
        )


def _decimal(value: str) -> Decimal:
    return Decimal(value or "0")


def _optional_decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value not in {None, ""} else None


def _millisecond_time(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1_000, UTC)


def _order_side(value: str) -> OrderSide:
    try:
        if value == "Buy":
            return OrderSide.BUY
        if value == "Sell":
            return OrderSide.SELL
        return OrderSide(value)
    except ValueError as exc:
        raise BrokerProviderError("Bybit returned an invalid order side") from exc


def _order_acknowledgement(result: Mapping[str, Any]) -> BrokerOrderAcknowledgement:
    try:
        return BrokerOrderAcknowledgement(
            order_id=result["orderId"],
            order_link_id=result["orderLinkId"],
        )
    except (KeyError, ValidationError) as exc:
        raise BrokerProviderError("Bybit returned an invalid order acknowledgement") from exc
