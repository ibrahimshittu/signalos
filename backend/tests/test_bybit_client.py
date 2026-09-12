from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from signalos_backend.brokers.domain import BrokerCredentialRejected, BrokerEnvironment
from signalos_backend.market.domain import MarketCategory
from signalos_backend.providers.bybit.client import (
    BybitHttpGateway,
    sign_get_request,
    sign_post_request,
)


def test_hmac_signature_matches_bybit_official_example():
    signature = sign_get_request(
        timestamp_ms=1_658_384_314_791,
        api_key="XXXXXXXXXX",
        api_secret="secret",
        recv_window_ms=5_000,
        query="category=option&symbol=BTC-29JUL22-25000-C",
    )

    assert signature == "02e9182e346177050f199ce1e0703d738589e3763805ed71590ced65539a73a7"


@pytest.mark.asyncio
async def test_key_environment_mismatch_is_a_non_retryable_credential_rejection():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api-testnet.bybit.com"
        return httpx.Response(
            200,
            json={
                "retCode": 10003,
                "retMsg": "API key is invalid.",
                "result": {},
                "time": 1,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = BybitHttpGateway(
        mainnet_base_url="https://api.bybit.com",
        testnet_base_url="https://api-testnet.bybit.com",
        client=client,
        clock_ms=lambda: 1_700_000_000_000,
    )

    with pytest.raises(BrokerCredentialRejected) as caught:
        await gateway.get_key_info(
            api_key="wrong-environment-key",
            api_secret="wrong-environment-secret",
            environment=BrokerEnvironment.TESTNET,
        )

    assert caught.value.code == 10003
    assert "selected Test account" in str(caught.value)
    assert "Demo Trading keys are not supported" in str(caught.value)
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticated_order_posts_the_exact_signed_ticket():
    received: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        received.append({"path": request.url.path, "body": json.loads(body)})
        expected = sign_post_request(
            timestamp_ms=1_700_000_000_000,
            api_key="write-key",
            api_secret="write-secret",
            recv_window_ms=5_000,
            body=body,
        )
        assert request.headers["X-BAPI-SIGN"] == expected
        result = {}
        if request.url.path == "/v5/order/create":
            result = {"orderId": "bybit-order-1", "orderLinkId": "sos-order-1"}
        return httpx.Response(
            200,
            json={"retCode": 0, "retMsg": "OK", "result": result, "time": 1},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = BybitHttpGateway(
        mainnet_base_url="https://api.bybit.com",
        testnet_base_url="https://api-testnet.bybit.com",
        client=client,
        clock_ms=lambda: 1_700_000_000_000,
    )
    await gateway.set_leverage(
        api_key="write-key",
        api_secret="write-secret",
        environment=BrokerEnvironment.MAINNET,
        category="linear",
        symbol="BTCUSDT",
        leverage="2",
    )
    acknowledgement = await gateway.place_order(
        api_key="write-key",
        api_secret="write-secret",
        environment=BrokerEnvironment.MAINNET,
        category="linear",
        symbol="BTCUSDT",
        side="Buy",
        order_type="Limit",
        quantity="0.01",
        price="68000",
        stop_loss="67000",
        take_profit="70000",
        order_link_id="sos-order-1",
    )

    assert acknowledgement.order_id == "bybit-order-1"
    assert [item["path"] for item in received] == [
        "/v5/position/set-leverage",
        "/v5/order/create",
    ]
    assert received[1]["body"] == {
        "category": "linear",
        "orderLinkId": "sos-order-1",
        "orderType": "Limit",
        "price": "68000",
        "qty": "0.01",
        "side": "Buy",
        "stopLoss": "67000",
        "symbol": "BTCUSDT",
        "takeProfit": "70000",
        "timeInForce": "GTC",
    }
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticated_monitoring_reads_orders_executions_and_positions():
    observed_ms = 1_776_163_200_000

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-BAPI-API-KEY"] == "write-key"
        if request.url.path == "/v5/order/realtime":
            result = {
                "list": [
                    {
                        "orderId": "order-1",
                        "orderLinkId": "sos-order-1",
                        "category": "linear",
                        "symbol": "BTCUSDT",
                        "side": "Buy",
                        "orderType": "Limit",
                        "orderStatus": "PartiallyFilled",
                        "qty": "0.02",
                        "cumExecQty": "0.01",
                        "leavesQty": "0.01",
                        "avgPrice": "68000",
                        "updatedTime": str(observed_ms),
                    }
                ],
                "nextPageCursor": "",
            }
        elif request.url.path == "/v5/execution/list":
            result = {
                "list": [
                    {
                        "execId": "execution-1",
                        "orderId": "order-1",
                        "orderLinkId": "sos-order-1",
                        "symbol": "BTCUSDT",
                        "side": "Buy",
                        "execPrice": "68000",
                        "execQty": "0.01",
                        "execValue": "680",
                        "execFee": "0.34",
                        "execTime": str(observed_ms),
                    }
                ],
                "nextPageCursor": "",
            }
        elif request.url.path == "/v5/position/list":
            result = {
                "list": [
                    {
                        "positionIdx": 0,
                        "symbol": "BTCUSDT",
                        "side": "Buy",
                        "size": "0.01",
                        "avgPrice": "68000",
                        "positionValue": "680",
                        "leverage": "",
                        "markPrice": "68100",
                        "liqPrice": "35000",
                        "takeProfit": "70000",
                        "stopLoss": "67000",
                        "unrealisedPnl": "1",
                        "cumRealisedPnl": "-0.34",
                        "seq": 42,
                        "updatedTime": str(observed_ms),
                    }
                ],
                "nextPageCursor": "",
            }
        else:  # pragma: no cover - makes unexpected broker calls obvious
            raise AssertionError(request.url.path)
        return httpx.Response(
            200,
            json={"retCode": 0, "retMsg": "OK", "result": result, "time": observed_ms},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = BybitHttpGateway(
        mainnet_base_url="https://api.bybit.com",
        testnet_base_url="https://api-testnet.bybit.com",
        client=client,
        clock_ms=lambda: observed_ms,
    )

    order = await gateway.get_order_snapshot(
        api_key="write-key",
        api_secret="write-secret",
        environment=BrokerEnvironment.MAINNET,
        category="linear",
        order_link_id="sos-order-1",
    )
    executions = await gateway.get_executions(
        api_key="write-key",
        api_secret="write-secret",
        environment=BrokerEnvironment.MAINNET,
        category="linear",
        start_time_ms=observed_ms - 60_000,
    )
    positions = await gateway.get_positions(
        api_key="write-key",
        api_secret="write-secret",
        environment=BrokerEnvironment.MAINNET,
        category="linear",
        settle_coin="USDT",
    )

    assert order is not None
    assert order.status == "PartiallyFilled"
    assert order.cumulative_executed_quantity == Decimal("0.01")
    assert executions[0].execution_id == "execution-1"
    assert executions[0].fee == Decimal("0.34")
    assert positions[0].position_index == 0
    assert positions[0].leverage is None
    assert positions[0].unrealised_pnl == Decimal("1")
    assert positions[0].updated_at == datetime.fromtimestamp(observed_ms / 1_000, UTC)
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticated_position_actions_are_explicit_and_reduce_only():
    received: list[tuple[str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        received.append((request.url.path, body))
        result = {"orderId": "close-order-1", "orderLinkId": body.get("orderLinkId", "")}
        return httpx.Response(
            200,
            json={"retCode": 0, "retMsg": "OK", "result": result, "time": 1},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = BybitHttpGateway(
        mainnet_base_url="https://api.bybit.com",
        testnet_base_url="https://api-testnet.bybit.com",
        client=client,
        clock_ms=lambda: 1_700_000_000_000,
    )

    await gateway.cancel_order(
        api_key="write-key",
        api_secret="write-secret",
        environment=BrokerEnvironment.MAINNET,
        category="linear",
        symbol="BTCUSDT",
        order_id="order-1",
        order_link_id="sos-order-1",
    )
    acknowledgement = await gateway.close_position(
        api_key="write-key",
        api_secret="write-secret",
        environment=BrokerEnvironment.MAINNET,
        category="linear",
        symbol="BTCUSDT",
        position_index=0,
        open_side="Buy",
        quantity="0.01",
        order_link_id="sos-close-1",
    )
    await gateway.set_trading_stop(
        api_key="write-key",
        api_secret="write-secret",
        environment=BrokerEnvironment.MAINNET,
        category="linear",
        symbol="BTCUSDT",
        position_index=0,
        stop_loss="67500",
        take_profit="70500",
    )

    assert acknowledgement.order_id == "close-order-1"
    assert received == [
        (
            "/v5/order/cancel",
            {
                "category": "linear",
                "orderId": "order-1",
                "orderLinkId": "sos-order-1",
                "symbol": "BTCUSDT",
            },
        ),
        (
            "/v5/order/create",
            {
                "category": "linear",
                "orderLinkId": "sos-close-1",
                "orderType": "Market",
                "positionIdx": 0,
                "qty": "0.01",
                "reduceOnly": True,
                "side": "Sell",
                "symbol": "BTCUSDT",
            },
        ),
        (
            "/v5/position/trading-stop",
            {
                "category": "linear",
                "positionIdx": 0,
                "stopLoss": "67500",
                "symbol": "BTCUSDT",
                "takeProfit": "70500",
                "tpslMode": "Full",
            },
        ),
    ]
    await client.aclose()


@pytest.mark.asyncio
async def test_order_monitoring_falls_back_to_history_for_terminal_orders() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        values = []
        if request.url.path == "/v5/order/history":
            values = [
                {
                    "orderId": "order-1",
                    "orderLinkId": "sos-order-1",
                    "category": "linear",
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "orderType": "Limit",
                    "orderStatus": "Cancelled",
                    "qty": "0.01",
                    "cumExecQty": "0",
                    "leavesQty": "0",
                    "avgPrice": "",
                    "updatedTime": "1776163200000",
                }
            ]
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {"list": values, "nextPageCursor": ""},
                "time": 1_776_163_200_000,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = BybitHttpGateway(
        mainnet_base_url="https://api.bybit.com",
        testnet_base_url="https://api-testnet.bybit.com",
        client=client,
    )

    snapshot = await gateway.get_order_snapshot(
        api_key="write-key",
        api_secret="write-secret",
        environment=BrokerEnvironment.MAINNET,
        category="linear",
        order_link_id="sos-order-1",
    )

    assert snapshot is not None
    assert snapshot.status == "Cancelled"
    assert paths == ["/v5/order/realtime", "/v5/order/history"]
    await client.aclose()


@pytest.mark.asyncio
async def test_public_market_adapter_paginates_linear_and_filters_usdt():
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        category = request.url.params["category"]
        cursor = request.url.params.get("cursor")
        if category == "spot":
            result = {
                "category": "spot",
                "nextPageCursor": "",
                "list": [instrument("BTCUSDT", "BTC", "USDT")],
            }
        elif cursor is None:
            result = {
                "category": "linear",
                "nextPageCursor": "next",
                "list": [linear_instrument("ETHUSDT", "ETH", "USDT", 480)],
            }
        else:
            result = {
                "category": "linear",
                "nextPageCursor": "",
                "list": [
                    linear_instrument("SOLUSDT", "SOL", "USDT", 240),
                    linear_instrument("BTCPERP", "BTC", "USDC", 480),
                ],
            }
        return httpx.Response(
            200,
            json={"retCode": 0, "retMsg": "OK", "result": result, "time": 1},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = BybitHttpGateway(
        mainnet_base_url="https://api.bybit.com",
        testnet_base_url="https://api-testnet.bybit.com",
        client=client,
    )

    instruments = await gateway.get_instruments(environment=BrokerEnvironment.MAINNET)

    assert [(item.category, item.symbol) for item in instruments] == [
        (MarketCategory.SPOT, "BTCUSDT"),
        (MarketCategory.LINEAR, "ETHUSDT"),
        (MarketCategory.LINEAR, "SOLUSDT"),
    ]
    assert instruments[1].funding_interval_minutes == 480
    assert instruments[2].funding_interval_minutes == 240
    assert len(requests) == 3
    assert "limit=1000" not in requests[0]
    assert "limit=1000" in requests[1]
    assert "cursor=next" in requests[2]
    await client.aclose()


@pytest.mark.asyncio
async def test_public_market_adapter_uses_spot_base_precision_as_quantity_step():
    """Bybit spot instruments do not expose the derivatives-only qtyStep field."""

    def handler(request: httpx.Request) -> httpx.Response:
        category = request.url.params["category"]
        values: list[dict[str, object]] = []
        if category == "spot":
            values = [
                {
                    "symbol": "BTCUSDT",
                    "status": "Trading",
                    "baseCoin": "BTC",
                    "quoteCoin": "USDT",
                    "priceFilter": {"tickSize": "0.1"},
                    "lotSizeFilter": {
                        "basePrecision": "0.000001",
                        "minOrderQty": "0.000011",
                        "minOrderAmt": "5",
                        "maxLimitOrderQty": "83",
                    },
                }
            ]
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {"category": category, "nextPageCursor": "", "list": values},
                "time": 1,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = BybitHttpGateway(
        mainnet_base_url="https://api.bybit.com",
        testnet_base_url="https://api-testnet.bybit.com",
        client=client,
    )

    instruments = await gateway.get_instruments(environment=BrokerEnvironment.MAINNET)

    assert len(instruments) == 1
    assert instruments[0].quantity_step == Decimal("0.000001")
    assert instruments[0].minimum_order_quantity == Decimal("0.000011")
    await client.aclose()


@pytest.mark.asyncio
async def test_public_market_adapter_treats_zero_funding_interval_as_unknown():
    """A zero interval from Bybit is not a valid funding schedule."""

    def handler(request: httpx.Request) -> httpx.Response:
        category = request.url.params["category"]
        values = (
            [linear_instrument("BTCUSDT", "BTC", "USDT", 0)]
            if category == "linear"
            else []
        )
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {"category": category, "nextPageCursor": "", "list": values},
                "time": 1,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = BybitHttpGateway(
        mainnet_base_url="https://api.bybit.com",
        testnet_base_url="https://api-testnet.bybit.com",
        client=client,
    )

    instruments = await gateway.get_instruments(environment=BrokerEnvironment.MAINNET)

    assert len(instruments) == 1
    assert instruments[0].funding_interval_minutes is None
    await client.aclose()


@pytest.mark.asyncio
async def test_public_market_adapter_parses_spot_and_linear_tickers():
    observed_ms = 1_776_163_200_000

    def handler(request: httpx.Request) -> httpx.Response:
        category = request.url.params["category"]
        values = [ticker_payload("BTCUSDT")]
        if category == "linear":
            values = [
                {
                    **ticker_payload("ETHUSDT"),
                    "openInterest": "1000",
                    "fundingRate": "0.0001",
                    "nextFundingTime": str(observed_ms + 3_600_000),
                }
            ]
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {"category": category, "list": values},
                "time": observed_ms,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = BybitHttpGateway(
        mainnet_base_url="https://api.bybit.com",
        testnet_base_url="https://api-testnet.bybit.com",
        client=client,
    )

    values = await gateway.get_tickers(environment=BrokerEnvironment.MAINNET)
    single = await gateway.get_ticker_snapshot(
        environment=BrokerEnvironment.MAINNET,
        category=MarketCategory.LINEAR,
        symbol="ETHUSDT",
    )

    assert [(item.category, item.symbol) for item in values] == [
        (MarketCategory.SPOT, "BTCUSDT"),
        (MarketCategory.LINEAR, "ETHUSDT"),
    ]
    assert values[0].observed_at == datetime.fromtimestamp(observed_ms / 1_000, UTC)
    assert values[1].open_interest == Decimal("1000")
    assert single.symbol == "ETHUSDT"
    assert values[1].next_funding_at == datetime.fromtimestamp(
        (observed_ms + 3_600_000) / 1_000, UTC
    )
    await client.aclose()


@pytest.mark.asyncio
async def test_public_market_adapter_reads_the_symbol_risk_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v5/market/risk-limit"
        assert dict(request.url.params) == {"category": "linear", "symbol": "BTCUSDT"}
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {
                    "category": "linear",
                    "list": [
                        {
                            "id": 2,
                            "symbol": "BTCUSDT",
                            "riskLimitValue": "2000000",
                            "maintenanceMargin": "0.01",
                            "initialMargin": "0.02",
                            "isLowestRisk": 0,
                            "maxLeverage": "50",
                            "mmDeduction": "0",
                        },
                        {
                            "id": 1,
                            "symbol": "BTCUSDT",
                            "riskLimitValue": "1000000",
                            "maintenanceMargin": "0.005",
                            "initialMargin": "0.01",
                            "isLowestRisk": 1,
                            "maxLeverage": "100",
                            "mmDeduction": "0",
                        },
                    ],
                    "nextPageCursor": "",
                },
                "time": 1,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = BybitHttpGateway(
        mainnet_base_url="https://api.bybit.com",
        testnet_base_url="https://api-testnet.bybit.com",
        client=client,
    )

    maximum = await gateway.get_max_leverage(
        environment=BrokerEnvironment.MAINNET,
        category=MarketCategory.LINEAR,
        symbol="BTCUSDT",
    )

    assert maximum == Decimal("100")
    await client.aclose()


@pytest.mark.asyncio
async def test_public_market_adapter_returns_only_completed_candles() -> None:
    now_ms = 1_776_163_200_000

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v5/market/kline"
        assert dict(request.url.params) == {
            "category": "linear",
            "interval": "15",
            "limit": "3",
            "symbol": "BTCUSDT",
        }
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {
                    "category": "linear",
                    "symbol": "BTCUSDT",
                    "list": [
                        [str(now_ms - 300_000), "103", "105", "102", "104", "10", "1040"],
                        [str(now_ms - 900_000), "102", "104", "101", "103", "9", "927"],
                        [str(now_ms - 1_800_000), "100", "103", "99", "102", "8", "816"],
                    ],
                },
                "time": now_ms,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = BybitHttpGateway(
        mainnet_base_url="https://api.bybit.com",
        testnet_base_url="https://api-testnet.bybit.com",
        client=client,
    )

    candles = await gateway.get_closed_klines(
        environment=BrokerEnvironment.MAINNET,
        category=MarketCategory.LINEAR,
        symbol="BTCUSDT",
        interval_minutes=15,
        limit=3,
    )

    assert [candle.close_price for candle in candles] == [Decimal("102"), Decimal("103")]
    assert all(candle.closed for candle in candles)
    assert candles[0].start_at < candles[1].start_at
    await client.aclose()


def instrument(symbol: str, base: str, quote: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "status": "Trading",
        "baseCoin": base,
        "quoteCoin": quote,
        "priceFilter": {"tickSize": "0.01"},
        "lotSizeFilter": {
            "qtyStep": "0.0001",
            "minOrderQty": "0.0001",
            "minOrderAmt": "5",
        },
    }


def linear_instrument(
    symbol: str, base: str, quote: str, funding_interval: int
) -> dict[str, object]:
    value = instrument(symbol, base, quote)
    value.update(
        {
            "settleCoin": quote,
            "contractType": "LinearPerpetual",
            "fundingInterval": funding_interval,
        }
    )
    value["lotSizeFilter"] = {
        "qtyStep": "0.001",
        "minOrderQty": "0.001",
        "minNotionalValue": "5",
    }
    return value


def ticker_payload(symbol: str) -> dict[str, str]:
    return {
        "symbol": symbol,
        "lastPrice": "100",
        "bid1Price": "99.9",
        "ask1Price": "100.1",
        "turnover24h": "1000000",
        "volume24h": "10000",
        "price24hPcnt": "0.02",
    }
