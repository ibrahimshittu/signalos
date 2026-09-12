from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from signalos_backend.brokers.domain import (
    AccountSnapshot,
    BrokerCredentialPurpose,
    BrokerOrderRejected,
    BrokerProviderError,
    ConnectionStatus,
)
from signalos_backend.brokers.store import BrokerStore
from signalos_backend.db import IntelligenceStore
from signalos_backend.domain import StrategyStatus, utc_now
from signalos_backend.execution.domain import (
    BrokerOrder,
    BrokerOrderAcknowledgement,
    BrokerOrderSnapshot,
    BrokerOrderState,
    BrokerPosition,
    BrokerPositionSnapshot,
    BrokerPositionState,
    ConfirmExecutionActionInput,
    ExecutionAction,
    ExecutionActionReview,
    ExecutionActionState,
    ExecutionActionTerms,
    ExecutionActionType,
    ExecutionConflictError,
    OrderReview,
    OrderTicket,
    SubmitOrderInput,
    UpdateProtectionInput,
)
from signalos_backend.execution.portfolio import position_portfolio_fingerprint
from signalos_backend.execution.reconciliation import map_order_state
from signalos_backend.execution.store import ExecutionStore
from signalos_backend.proposals.domain import OrderSide, OrderType, ProposalStatus, TradeProposal
from signalos_backend.proposals.store import ProposalStore
from signalos_backend.security.credentials import CredentialCipher
from signalos_backend.users.store import UserStore


class BrokerExecutionGateway(Protocol):
    async def set_leverage(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment,
        category: str,
        symbol: str,
        leverage: str,
    ) -> None: ...

    async def place_order(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment,
        category: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: str | None,
        stop_loss: str,
        take_profit: str,
        order_link_id: str,
    ) -> BrokerOrderAcknowledgement: ...

    async def get_order_snapshot(self, **kwargs) -> BrokerOrderSnapshot | None: ...

    async def get_positions(self, **kwargs) -> tuple[BrokerPositionSnapshot, ...]: ...

    async def cancel_order(self, **kwargs) -> BrokerOrderAcknowledgement: ...

    async def close_position(self, **kwargs) -> BrokerOrderAcknowledgement: ...

    async def set_trading_stop(self, **kwargs) -> None: ...

    async def get_account_snapshot(self, **kwargs) -> AccountSnapshot: ...

    async def get_max_leverage(self, **kwargs) -> Decimal: ...

    async def get_ticker_snapshot(self, **kwargs): ...


class ExecutionService:
    def __init__(
        self,
        *,
        proposals: ProposalStore,
        users: UserStore,
        intelligence: IntelligenceStore,
        brokers: BrokerStore,
        executions: ExecutionStore,
        cipher: CredentialCipher,
        gateway: BrokerExecutionGateway,
        clock: Callable[[], datetime] = utc_now,
        review_ttl: timedelta = timedelta(minutes=2),
    ) -> None:
        self.proposals = proposals
        self.users = users
        self.intelligence = intelligence
        self.brokers = brokers
        self.executions = executions
        self.cipher = cipher
        self.gateway = gateway
        self.clock = clock
        self.review_ttl = review_ttl

    async def review(self, *, user_id: str, proposal_id: UUID) -> OrderReview:
        proposal = await self._require_proposal(user_id=user_id, proposal_id=proposal_id)
        now = self.clock().astimezone(UTC)
        if proposal.status is not ProposalStatus.AVAILABLE:
            raise ExecutionConflictError("proposal is not available")
        if proposal.expires_at <= now:
            raise ExecutionConflictError("proposal expired")
        if proposal.order_type is not OrderType.LIMIT or proposal.limit_price is None:
            raise ExecutionConflictError(
                "market orders are disabled until bounded slippage is part of the reviewed ticket; "
                "a bounded limit price is required"
            )
        ticket = self._ticket(proposal)
        return await self.executions.create_review(
            user_id=user_id,
            ticket=ticket,
            now=now,
            expires_at=min(proposal.expires_at, now + self.review_ttl),
        )

    async def submit(
        self,
        *,
        user_id: str,
        proposal_id: UUID,
        payload: SubmitOrderInput,
    ) -> BrokerOrder:
        existing = await self.executions.get_order_by_idempotency(
            user_id=user_id, idempotency_key=payload.idempotency_key
        )
        if existing is not None:
            if existing.proposal_id != proposal_id:
                raise ExecutionConflictError("idempotency key belongs to another proposal")
            return existing
        proposal = await self._require_proposal(user_id=user_id, proposal_id=proposal_id)
        credentials = await self._preflight_submission(user_id=user_id, proposal=proposal)
        now = self.clock().astimezone(UTC)
        start = await self.executions.begin_submission(
            user_id=user_id,
            proposal_id=proposal_id,
            payload=payload,
            now=now,
        )
        if not start.is_new:
            return start.order

        api_key, api_secret = credentials
        proposal = start.proposal
        try:
            if proposal.category.value == "linear":
                await self.gateway.set_leverage(
                    api_key=api_key,
                    api_secret=api_secret,
                    environment=start.order.environment,
                    category=proposal.category.value,
                    symbol=proposal.symbol,
                    leverage=str(proposal.leverage),
                )
            acknowledgement = await self.gateway.place_order(
                api_key=api_key,
                api_secret=api_secret,
                environment=start.order.environment,
                category=proposal.category.value,
                symbol=proposal.symbol,
                side=proposal.side.value.title(),
                order_type=proposal.order_type.value.title(),
                quantity=str(proposal.quantity),
                price=str(proposal.limit_price) if proposal.limit_price is not None else None,
                stop_loss=str(proposal.stop_loss),
                take_profit=str(proposal.take_profit),
                order_link_id=start.order.broker_order_link_id,
            )
        except BrokerOrderRejected as exc:
            return await self.executions.mark_failed(
                order_id=start.order.id,
                state=BrokerOrderState.REJECTED,
                error_code=f"bybit_{exc.code}",
                now=self.clock().astimezone(UTC),
            )
        except BrokerProviderError:
            return await self.executions.mark_failed(
                order_id=start.order.id,
                state=BrokerOrderState.SUBMISSION_UNKNOWN,
                error_code="bybit_transport_unknown",
                now=self.clock().astimezone(UTC),
            )
        if acknowledgement.order_link_id != start.order.broker_order_link_id:
            return await self.executions.mark_failed(
                order_id=start.order.id,
                state=BrokerOrderState.SUBMISSION_UNKNOWN,
                error_code="bybit_order_link_mismatch",
                now=self.clock().astimezone(UTC),
            )
        return await self.executions.mark_acknowledged(
            order_id=start.order.id,
            broker_order_id=acknowledgement.order_id,
            now=self.clock().astimezone(UTC),
        )

    async def _preflight_submission(
        self, *, user_id: str, proposal: TradeProposal
    ) -> tuple[str, str]:
        now = self.clock().astimezone(UTC)
        if proposal.status is not ProposalStatus.AVAILABLE or proposal.expires_at <= now:
            raise ExecutionConflictError("proposal is no longer available")
        profile = await self.users.get_profile(user_id)
        if profile is None or not profile.disclosures_accepted:
            raise ExecutionConflictError("current mandate requires an accepted investment profile")
        mandate = profile.adaptive_mandate
        if proposal.leverage > mandate.max_leverage or (
            proposal.category.value == "linear" and not mandate.derivatives_eligible
        ):
            raise ExecutionConflictError("proposal no longer fits the current mandate")
        strategy = await self.intelligence.get_strategy(
            proposal.strategy_id, proposal.strategy_version
        )
        if strategy is None or strategy.status is not StrategyStatus.APPROVED:
            raise ExecutionConflictError("strategy is no longer approved; request a new review")
        evaluation = await self.intelligence.latest_evaluation(strategy.id, strategy.version)
        if (
            evaluation is None
            or not evaluation.passed_gates
            or f"evaluation:{evaluation.reproducibility_hash}" not in strategy.evidence_references
        ):
            raise ExecutionConflictError("strategy evidence is unavailable; request a new review")
        if (
            proposal.required_margin is None
            or proposal.portfolio_fingerprint is None
            or proposal.position_reconciled_at is None
        ):
            raise ExecutionConflictError("proposal lacks submit-time portfolio binding")
        connection = await self.brokers.get_connection(
            user_id=user_id, connection_id=proposal.connection_id
        )
        context = await self.brokers.get_context(user_id=user_id)
        if (
            connection is None
            or connection.status is not ConnectionStatus.HEALTHY
            or connection.environment is not proposal.environment
            or context is None
            or context.connection_id != proposal.connection_id
        ):
            raise ExecutionConflictError("proposal does not match the active healthy account")
        category_enabled = connection is not None and (
            (proposal.category.value == "spot" and connection.spot_trading_enabled)
            or (proposal.category.value == "linear" and connection.derivatives_trading_enabled)
        )
        if not category_enabled:
            raise ExecutionConflictError("Bybit key does not permit this market category")
        credentials = await self._credentials(user_id=user_id, connection_id=proposal.connection_id)
        if credentials is None:
            raise ExecutionConflictError("broker credential is unavailable")
        account = await self.gateway.get_account_snapshot(
            api_key=credentials[0],
            api_secret=credentials[1],
            environment=proposal.environment,
        )
        positions = await self.gateway.get_positions(
            api_key=credentials[0],
            api_secret=credentials[1],
            environment=proposal.environment,
            category="linear",
            settle_coin="USDT",
        )
        await self.executions.replace_open_positions(
            user_id=user_id,
            connection_id=proposal.connection_id,
            environment=proposal.environment,
            snapshots=positions,
            reconciled_at=now,
        )
        portfolio = await self.executions.get_position_portfolio(
            user_id=user_id, connection_id=proposal.connection_id
        )
        if portfolio is None or not hmac.compare_digest(
            position_portfolio_fingerprint(portfolio.positions),
            proposal.portfolio_fingerprint,
        ):
            raise ExecutionConflictError("portfolio changed after proposal; request a new proposal")
        broker_max_leverage = await self.gateway.get_max_leverage(
            environment=proposal.environment,
            category=proposal.category,
            symbol=proposal.symbol,
        )
        if proposal.leverage > broker_max_leverage:
            raise ExecutionConflictError("Bybit leverage limit changed after proposal")
        ticker = await self.gateway.get_ticker_snapshot(
            environment=proposal.environment,
            category=proposal.category,
            symbol=proposal.symbol,
        )
        if proposal.side is OrderSide.BUY:
            boundaries_valid = proposal.stop_loss < ticker.last_price < proposal.take_profit
        else:
            boundaries_valid = proposal.take_profit < ticker.last_price < proposal.stop_loss
        if not boundaries_valid:
            raise ExecutionConflictError(
                "market crossed a reviewed boundary; request a new proposal"
            )
        entry = proposal.limit_price or proposal.market_price
        recomputed_margin = proposal.quantity * entry / proposal.leverage
        if abs(recomputed_margin - proposal.required_margin) > Decimal("0.01"):
            raise ExecutionConflictError("reviewed margin no longer matches the order terms")
        cash_required = (
            proposal.required_margin + proposal.estimated_fees + proposal.estimated_slippage
        )
        if account.available_balance < cash_required:
            raise ExecutionConflictError("available margin changed after proposal")
        if proposal.estimated_max_loss > account.total_equity * mandate.max_loss_per_trade_pct:
            raise ExecutionConflictError(
                "proposal loss exceeds the current mandate on fresh equity"
            )
        return credentials

    async def get_order(self, *, user_id: str, order_id: UUID) -> BrokerOrder | None:
        return await self.executions.get_order(user_id=user_id, order_id=order_id)

    async def list_orders(
        self, *, user_id: str, limit: int = 50, offset: int = 0, proposal_id: UUID | None = None
    ) -> tuple[BrokerOrder, ...]:
        return await self.executions.list_orders(
            user_id=user_id, limit=limit, offset=offset, proposal_id=proposal_id
        )

    async def list_positions(
        self,
        *,
        user_id: str,
        open_only: bool = True,
        limit: int = 100,
        offset: int = 0,
        connection_id: UUID | None = None,
    ) -> tuple[BrokerPosition, ...]:
        return await self.executions.list_positions(
            user_id=user_id,
            open_only=open_only,
            connection_id=connection_id,
            limit=limit,
            offset=offset,
        )

    async def get_position(self, *, user_id: str, position_id: UUID) -> BrokerPosition | None:
        return await self.executions.get_position(user_id=user_id, position_id=position_id)

    async def get_action(self, *, user_id: str, action_id: UUID) -> ExecutionAction | None:
        return await self.executions.get_action(user_id=user_id, action_id=action_id)

    async def review_cancel_order(self, *, user_id: str, order_id: UUID) -> ExecutionActionReview:
        order = await self.executions.get_order(user_id=user_id, order_id=order_id)
        if order is None:
            raise KeyError(order_id)
        order = await self._refresh_order(user_id=user_id, order=order)
        if order.state not in {
            BrokerOrderState.ACKNOWLEDGED,
            BrokerOrderState.PARTIALLY_FILLED,
        }:
            raise ExecutionConflictError(f"order cannot be cancelled from {order.state}")
        if not order.category or not order.symbol or not order.broker_order_id:
            raise ExecutionConflictError("order has not been reconciled with Bybit")
        terms = ExecutionActionTerms(
            action_type=ExecutionActionType.CANCEL_ORDER,
            target_id=order.id,
            connection_id=order.connection_id,
            environment=order.environment,
            category=order.category,
            symbol=order.symbol,
            broker_order_id=order.broker_order_id,
            broker_order_link_id=order.broker_order_link_id,
            broker_status=order.broker_status,
            quantity=order.leaves_quantity,
        )
        return await self._create_action_review(user_id=user_id, terms=terms)

    async def cancel_order(
        self,
        *,
        user_id: str,
        order_id: UUID,
        payload: ConfirmExecutionActionInput,
    ) -> ExecutionAction:
        existing = await self._existing_action(
            user_id=user_id,
            target_id=order_id,
            action_type=ExecutionActionType.CANCEL_ORDER,
            idempotency_key=payload.idempotency_key,
        )
        if existing is not None:
            return existing
        review = await self._require_action_review(
            user_id=user_id,
            target_id=order_id,
            action_type=ExecutionActionType.CANCEL_ORDER,
            payload=payload,
        )
        order = await self.executions.get_order(user_id=user_id, order_id=order_id)
        if order is None:
            raise KeyError(order_id)
        order = await self._refresh_order(user_id=user_id, order=order)
        if (
            order.state not in {BrokerOrderState.ACKNOWLEDGED, BrokerOrderState.PARTIALLY_FILLED}
            or order.broker_status != review.terms.broker_status
            or order.leaves_quantity != review.terms.quantity
        ):
            raise ExecutionConflictError("order changed after review; create a new cancel review")
        start = await self.executions.begin_action(
            user_id=user_id,
            action_type=ExecutionActionType.CANCEL_ORDER,
            target_id=order_id,
            payload=payload,
            now=self.clock().astimezone(UTC),
        )
        if not start.is_new:
            return start.action
        credentials = await self._credentials(user_id=user_id, connection_id=order.connection_id)
        if credentials is None:
            return await self._reject_action(start.action.id, "credential_unavailable")
        try:
            acknowledgement = await self.gateway.cancel_order(
                api_key=credentials[0],
                api_secret=credentials[1],
                environment=order.environment,
                category=start.terms.category.value,
                symbol=start.terms.symbol,
                order_id=start.terms.broker_order_id,
                order_link_id=start.terms.broker_order_link_id,
            )
        except BrokerOrderRejected as exc:
            return await self._reject_action(start.action.id, f"bybit_{exc.code}")
        except BrokerProviderError:
            return await self._unknown_action(start.action.id, "bybit_transport_unknown")
        if acknowledgement.order_id != start.terms.broker_order_id:
            return await self._unknown_action(start.action.id, "bybit_order_id_mismatch")
        return await self._acknowledge_action(start.action.id, acknowledgement.order_id)

    async def review_close_position(
        self, *, user_id: str, position_id: UUID
    ) -> ExecutionActionReview:
        position = await self._refresh_position(user_id=user_id, position_id=position_id)
        terms = self._position_terms(
            position=position,
            action_type=ExecutionActionType.CLOSE_POSITION,
        )
        return await self._create_action_review(user_id=user_id, terms=terms)

    async def close_position(
        self,
        *,
        user_id: str,
        position_id: UUID,
        payload: ConfirmExecutionActionInput,
    ) -> ExecutionAction:
        existing = await self._existing_action(
            user_id=user_id,
            target_id=position_id,
            action_type=ExecutionActionType.CLOSE_POSITION,
            idempotency_key=payload.idempotency_key,
        )
        if existing is not None:
            return existing
        review = await self._require_action_review(
            user_id=user_id,
            target_id=position_id,
            action_type=ExecutionActionType.CLOSE_POSITION,
            payload=payload,
        )
        position = await self._refresh_position(user_id=user_id, position_id=position_id)
        self._require_position_unchanged(position, review.terms)
        start = await self.executions.begin_action(
            user_id=user_id,
            action_type=ExecutionActionType.CLOSE_POSITION,
            target_id=position_id,
            payload=payload,
            now=self.clock().astimezone(UTC),
        )
        if not start.is_new:
            return start.action
        credentials = await self._credentials(user_id=user_id, connection_id=position.connection_id)
        if credentials is None:
            return await self._reject_action(start.action.id, "credential_unavailable")
        try:
            acknowledgement = await self.gateway.close_position(
                api_key=credentials[0],
                api_secret=credentials[1],
                environment=position.environment,
                category=position.category.value,
                symbol=position.symbol,
                position_index=position.position_index,
                open_side=position.side.value.title(),
                quantity=str(position.size),
                order_link_id=start.action.broker_order_link_id,
            )
        except BrokerOrderRejected as exc:
            return await self._reject_action(start.action.id, f"bybit_{exc.code}")
        except BrokerProviderError:
            return await self._unknown_action(start.action.id, "bybit_transport_unknown")
        if acknowledgement.order_link_id != start.action.broker_order_link_id:
            return await self._unknown_action(start.action.id, "bybit_order_link_mismatch")
        return await self._acknowledge_action(start.action.id, acknowledgement.order_id)

    async def review_position_protection(
        self,
        *,
        user_id: str,
        position_id: UUID,
        payload: UpdateProtectionInput,
    ) -> ExecutionActionReview:
        position = await self._refresh_position(user_id=user_id, position_id=position_id)
        stop_loss = payload.stop_loss if payload.stop_loss is not None else position.stop_loss
        take_profit = (
            payload.take_profit if payload.take_profit is not None else position.take_profit
        )
        self._validate_protection(position, stop_loss=stop_loss, take_profit=take_profit)
        terms = self._position_terms(
            position=position,
            action_type=ExecutionActionType.UPDATE_PROTECTION,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        return await self._create_action_review(user_id=user_id, terms=terms)

    async def update_position_protection(
        self,
        *,
        user_id: str,
        position_id: UUID,
        payload: ConfirmExecutionActionInput,
    ) -> ExecutionAction:
        existing = await self._existing_action(
            user_id=user_id,
            target_id=position_id,
            action_type=ExecutionActionType.UPDATE_PROTECTION,
            idempotency_key=payload.idempotency_key,
        )
        if existing is not None:
            return existing
        review = await self._require_action_review(
            user_id=user_id,
            target_id=position_id,
            action_type=ExecutionActionType.UPDATE_PROTECTION,
            payload=payload,
        )
        position = await self._refresh_position(user_id=user_id, position_id=position_id)
        self._require_position_unchanged(position, review.terms)
        self._validate_protection(
            position,
            stop_loss=review.terms.stop_loss,
            take_profit=review.terms.take_profit,
        )
        start = await self.executions.begin_action(
            user_id=user_id,
            action_type=ExecutionActionType.UPDATE_PROTECTION,
            target_id=position_id,
            payload=payload,
            now=self.clock().astimezone(UTC),
        )
        if not start.is_new:
            return start.action
        credentials = await self._credentials(user_id=user_id, connection_id=position.connection_id)
        if credentials is None:
            return await self._reject_action(start.action.id, "credential_unavailable")
        try:
            await self.gateway.set_trading_stop(
                api_key=credentials[0],
                api_secret=credentials[1],
                environment=position.environment,
                category=position.category.value,
                symbol=position.symbol,
                position_index=position.position_index,
                stop_loss=str(review.terms.stop_loss or Decimal("0")),
                take_profit=str(review.terms.take_profit or Decimal("0")),
            )
        except BrokerOrderRejected as exc:
            return await self._reject_action(start.action.id, f"bybit_{exc.code}")
        except BrokerProviderError:
            return await self._unknown_action(start.action.id, "bybit_transport_unknown")
        return await self._acknowledge_action(start.action.id)

    async def _require_proposal(self, *, user_id: str, proposal_id: UUID) -> TradeProposal:
        proposal = await self.proposals.get(user_id=user_id, proposal_id=proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        return proposal

    async def _create_action_review(
        self, *, user_id: str, terms: ExecutionActionTerms
    ) -> ExecutionActionReview:
        now = self.clock().astimezone(UTC)
        return await self.executions.create_action_review(
            user_id=user_id,
            terms=terms,
            action_hash=self._action_hash(terms),
            now=now,
            expires_at=now + self.review_ttl,
        )

    async def _existing_action(
        self,
        *,
        user_id: str,
        target_id: UUID,
        action_type: ExecutionActionType,
        idempotency_key: str,
    ) -> ExecutionAction | None:
        action = await self.executions.get_action_by_idempotency(
            user_id=user_id, idempotency_key=idempotency_key
        )
        if action is None:
            return None
        if action.target_id != target_id or action.action_type is not action_type:
            raise ExecutionConflictError("idempotency key belongs to another action")
        return action

    async def _require_action_review(
        self,
        *,
        user_id: str,
        target_id: UUID,
        action_type: ExecutionActionType,
        payload: ConfirmExecutionActionInput,
    ) -> ExecutionActionReview:
        review = await self.executions.get_action_review(
            user_id=user_id, review_id=payload.review_id
        )
        if review is None or review.terms.target_id != target_id:
            raise KeyError(target_id)
        now = self.clock().astimezone(UTC)
        if review.expires_at <= now:
            raise ExecutionConflictError("execution action review expired")
        if review.terms.action_type is not action_type:
            raise ExecutionConflictError("review is for a different execution action")
        if not hmac.compare_digest(review.action_hash, payload.action_hash):
            raise ExecutionConflictError("action hash does not match the reviewed action")
        return review

    async def _refresh_order(self, *, user_id: str, order: BrokerOrder) -> BrokerOrder:
        if order.category is None:
            raise ExecutionConflictError("order category is unavailable")
        credentials = await self._credentials(user_id=user_id, connection_id=order.connection_id)
        if credentials is None:
            raise ExecutionConflictError("broker credential is unavailable")
        snapshot = await self.gateway.get_order_snapshot(
            api_key=credentials[0],
            api_secret=credentials[1],
            environment=order.environment,
            category=order.category.value,
            order_link_id=order.broker_order_link_id,
        )
        if snapshot is None:
            raise ExecutionConflictError("Bybit order state is not yet available")
        await self.executions.reconcile_order(
            order_id=order.id,
            snapshot=snapshot,
            state=map_order_state(snapshot.status),
            reconciled_at=self.clock().astimezone(UTC),
        )
        refreshed = await self.executions.get_order(user_id=user_id, order_id=order.id)
        if refreshed is None:  # pragma: no cover - durable ownership contract
            raise KeyError(order.id)
        return refreshed

    async def _refresh_position(self, *, user_id: str, position_id: UUID) -> BrokerPosition:
        position = await self.executions.get_position(user_id=user_id, position_id=position_id)
        if position is None:
            raise KeyError(position_id)
        credentials = await self._credentials(user_id=user_id, connection_id=position.connection_id)
        if credentials is None:
            raise ExecutionConflictError("broker credential is unavailable")
        snapshots = await self.gateway.get_positions(
            api_key=credentials[0],
            api_secret=credentials[1],
            environment=position.environment,
            category=position.category.value,
            settle_coin="USDT",
        )
        await self.executions.replace_open_positions(
            user_id=user_id,
            connection_id=position.connection_id,
            environment=position.environment,
            snapshots=snapshots,
            reconciled_at=self.clock().astimezone(UTC),
        )
        refreshed = await self.executions.get_position(user_id=user_id, position_id=position_id)
        if refreshed is None or refreshed.state is not BrokerPositionState.OPEN:
            raise ExecutionConflictError("position is no longer open")
        return refreshed

    async def _credentials(self, *, user_id: str, connection_id: UUID) -> tuple[str, str] | None:
        encrypted = await self.brokers.get_credential_ciphertexts(
            user_id=user_id,
            connection_id=connection_id,
            purpose=BrokerCredentialPurpose.BROKER_ACCESS,
        )
        if encrypted is None:
            return None
        return self.cipher.decrypt(encrypted[0]), self.cipher.decrypt(encrypted[1])

    async def _acknowledge_action(
        self, action_id: UUID, broker_order_id: str | None = None
    ) -> ExecutionAction:
        return await self.executions.mark_action(
            action_id=action_id,
            state=ExecutionActionState.ACKNOWLEDGED,
            broker_order_id=broker_order_id,
            now=self.clock().astimezone(UTC),
        )

    async def _reject_action(self, action_id: UUID, error_code: str) -> ExecutionAction:
        return await self.executions.mark_action(
            action_id=action_id,
            state=ExecutionActionState.REJECTED,
            error_code=error_code,
            now=self.clock().astimezone(UTC),
        )

    async def _unknown_action(self, action_id: UUID, error_code: str) -> ExecutionAction:
        return await self.executions.mark_action(
            action_id=action_id,
            state=ExecutionActionState.RECONCILIATION_REQUIRED,
            error_code=error_code,
            now=self.clock().astimezone(UTC),
        )

    @staticmethod
    def _position_terms(
        *,
        position: BrokerPosition,
        action_type: ExecutionActionType,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
    ) -> ExecutionActionTerms:
        return ExecutionActionTerms(
            action_type=action_type,
            target_id=position.id,
            connection_id=position.connection_id,
            environment=position.environment,
            category=position.category,
            symbol=position.symbol,
            position_index=position.position_index,
            side=position.side,
            quantity=position.size,
            target_sequence=position.sequence,
            mark_price=position.mark_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    @staticmethod
    def _require_position_unchanged(position: BrokerPosition, terms: ExecutionActionTerms) -> None:
        if (
            position.sequence != terms.target_sequence
            or position.size != terms.quantity
            or position.side is not terms.side
        ):
            raise ExecutionConflictError("position changed after review; create a new review")

    @staticmethod
    def _validate_protection(
        position: BrokerPosition,
        *,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> None:
        if stop_loss is None and take_profit is None:
            raise ExecutionConflictError("position protection cannot remove both boundaries")
        if position.side is OrderSide.BUY:
            valid = (stop_loss is None or stop_loss < position.mark_price) and (
                take_profit is None or take_profit > position.mark_price
            )
        else:
            valid = (stop_loss is None or stop_loss > position.mark_price) and (
                take_profit is None or take_profit < position.mark_price
            )
        if not valid:
            raise ExecutionConflictError(
                "stop loss and take profit must remain on protective sides of the mark price"
            )

    @staticmethod
    def _action_hash(terms: ExecutionActionTerms) -> str:
        return hashlib.sha256(terms.model_dump_json(exclude_none=False).encode("utf-8")).hexdigest()

    @staticmethod
    def _ticket(proposal: TradeProposal) -> OrderTicket:
        return OrderTicket(
            proposal_id=proposal.id,
            proposal_hash=proposal.proposal_hash,
            provider_id="bybit",
            environment=proposal.environment,
            category=proposal.category,
            symbol=proposal.symbol,
            side=proposal.side,
            order_type=proposal.order_type,
            quantity=proposal.quantity,
            limit_price=proposal.limit_price,
            stop_loss=proposal.stop_loss,
            take_profit=proposal.take_profit,
            leverage=proposal.leverage,
            estimated_max_loss=proposal.estimated_max_loss,
            proposal_expires_at=proposal.expires_at,
        )
