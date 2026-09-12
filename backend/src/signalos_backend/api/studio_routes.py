from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse

from signalos_backend.brokers.domain import (
    BrokerContextSwitch,
    BrokerCredentialRejected,
    BrokerEnvironment,
    BrokerPolicyError,
    BrokerProviderError,
    CreateBrokerConnection,
)
from signalos_backend.execution.domain import (
    ConfirmExecutionActionInput,
    ExecutionConflictError,
    SubmitOrderInput,
    UpdateProtectionInput,
)
from signalos_backend.identity import Principal, require_execution_principal, require_principal
from signalos_backend.market.service import MarketDataError
from signalos_backend.notifications.domain import RegisterPushDevice
from signalos_backend.proposals.domain import ProposalConflictError, ProposalFeedback
from signalos_backend.studio import StudioServices
from signalos_backend.users.domain import InvestmentProfileInput, PersonalizedPreferencesUpdate

router = APIRouter(prefix="/v1", dependencies=[Depends(require_principal)])


def get_studio(request: Request) -> StudioServices:
    return request.app.state.studio


@router.get("/market-scans/latest")
async def latest_market_scan(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
    environment: BrokerEnvironment = BrokerEnvironment.MAINNET,
):
    del principal
    return await studio.markets.latest_scan(environment=environment)


@router.post("/market-scans", status_code=status.HTTP_201_CREATED)
async def create_market_scan(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
    environment: BrokerEnvironment = BrokerEnvironment.MAINNET,
):
    del principal
    try:
        return await studio.markets.run_scan(environment=environment)
    except MarketDataError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"code": "market_data_unavailable", "detail": str(exc)},
        )


@router.get("/market-reviews/latest")
async def latest_market_review(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
    environment: BrokerEnvironment = BrokerEnvironment.MAINNET,
):
    review = await studio.markets.latest_review(environment=environment)
    context = await studio.brokers.store.get_context(user_id=principal.user_id)
    if review is None or context is None or context.environment is not environment:
        return review
    return await studio.markets.store.review_for_account(
        review, user_id=principal.user_id, connection_id=context.connection_id
    )


@router.post("/market-analysis-requests", status_code=status.HTTP_202_ACCEPTED)
async def request_market_analysis(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
    environment: BrokerEnvironment = BrokerEnvironment.MAINNET,
):
    return await studio.markets.request_analysis(
        user_id=principal.user_id,
        environment=environment,
    )


@router.get("/market-analysis-requests/{request_id}")
async def get_market_analysis_request(
    request_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    analysis_request = await studio.markets.analysis_request(
        user_id=principal.user_id,
        request_id=str(request_id),
    )
    if analysis_request is None:
        raise HTTPException(status_code=404, detail="market analysis request not found")
    return analysis_request


@router.get("/broker-providers")
async def list_broker_providers(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    del principal
    return studio.brokers.providers()


@router.get("/portfolio-summary")
async def portfolio_summary(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    summary = await studio.brokers.portfolio_summary(user_id=principal.user_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="portfolio summary not found")
    return summary


@router.post("/broker-context/switch")
async def switch_broker_context(
    payload: BrokerContextSwitch,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.broker_contexts.switch(user_id=principal.user_id, payload=payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="broker connection not found") from exc
    except BrokerPolicyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/me/onboarding-state")
async def onboarding_state(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    return await studio.users.onboarding_state(user_id=principal.user_id)


@router.get("/me/investment-profile")
async def get_investment_profile(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    profile = await studio.users.get_profile(user_id=principal.user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="investment profile not found")
    return profile


@router.put("/me/investment-profile")
async def put_investment_profile(
    payload: InvestmentProfileInput,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    return await studio.users.save_profile(user_id=principal.user_id, payload=payload)


@router.get("/me/personalization")
async def get_personalized_policy(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    policy = await studio.users.get_personalized_policy(user_id=principal.user_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="personalized policy not found")
    return policy


@router.post("/me/personalization/generate")
async def generate_personalized_policy(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.users.generate_personalized_policy(user_id=principal.user_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=409,
            detail="complete your investment profile first",
        ) from exc


@router.put("/me/personalization")
async def update_personalized_policy(
    payload: PersonalizedPreferencesUpdate,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    policy = await studio.users.update_personalized_policy(
        user_id=principal.user_id,
        payload=payload,
    )
    if policy is None:
        raise HTTPException(status_code=404, detail="personalized policy not found")
    return policy


@router.get("/me/memory")
async def list_user_memory(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await studio.users.list_memories(user_id=principal.user_id, limit=limit, offset=offset)


@router.delete("/me/memory/{memory_id}", status_code=204)
async def delete_user_memory(
    memory_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
) -> Response:
    deleted = await studio.users.delete_memory(user_id=principal.user_id, memory_id=memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="memory not found")
    return Response(status_code=204)


@router.post("/me/memory/reset-learned-preferences", status_code=204)
async def reset_learned_preferences(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
) -> Response:
    await studio.users.reset_learned_preferences(user_id=principal.user_id)
    return Response(status_code=204)


@router.put("/me/notification-devices/{installation_id}")
async def register_notification_device(
    installation_id: UUID,
    payload: RegisterPushDevice,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.notifications.register_device(
            user_id=principal.user_id,
            installation_id=installation_id,
            payload=payload,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/me/notification-devices")
async def list_notification_devices(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    return await studio.notifications.list_devices(user_id=principal.user_id)


@router.delete("/me/notification-devices/{installation_id}", status_code=204)
async def remove_notification_device(
    installation_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
) -> Response:
    removed = await studio.notifications.remove_device(
        user_id=principal.user_id,
        installation_id=installation_id,
    )
    if not removed:
        raise HTTPException(status_code=404, detail="notification device not found")
    return Response(status_code=204)


@router.post("/broker-connections", status_code=status.HTTP_201_CREATED)
async def create_broker_connection(
    payload: CreateBrokerConnection,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    profile = await studio.users.get_profile(user_id=principal.user_id)
    if profile is None or not profile.disclosures_accepted:
        raise HTTPException(
            status_code=409,
            detail="complete profile and disclosures before connecting a broker",
        )
    try:
        return await studio.brokers.create(user_id=principal.user_id, payload=payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/broker-connections/{connection_id}")
async def get_broker_connection(
    connection_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    connection = await studio.brokers.get(user_id=principal.user_id, connection_id=connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="broker connection not found")
    return connection


@router.delete("/broker-connections/{connection_id}", status_code=204)
async def revoke_broker_connection(
    connection_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
) -> Response:
    try:
        await studio.broker_contexts.revoke(
            user_id=principal.user_id,
            connection_id=connection_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="broker connection not found") from exc
    return Response(status_code=204)


@router.post("/broker-connections/{connection_id}/verify")
async def verify_broker_connection(
    connection_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.brokers.verify(user_id=principal.user_id, connection_id=connection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="broker connection not found") from exc
    except BrokerPolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BrokerCredentialRejected as exc:
        code = "bybit_environment_mismatch" if exc.code == 10003 else "bybit_credentials_rejected"
        return JSONResponse(
            status_code=422,
            content={"code": code, "detail": str(exc)},
        )
    except BrokerProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/broker-connections/{connection_id}/sync")
async def sync_broker_connection(
    connection_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.brokers.sync(user_id=principal.user_id, connection_id=connection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="broker connection not found") from exc
    except BrokerPolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BrokerProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/trade-proposals")
async def list_trade_proposals(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    connection_id: UUID | None = None,
):
    return await studio.proposals.list(
        user_id=principal.user_id, limit=limit, offset=offset, connection_id=connection_id
    )


@router.get("/trade-proposals/{proposal_id}")
async def get_trade_proposal(
    proposal_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    proposal = await studio.proposals.get(
        user_id=principal.user_id,
        proposal_id=proposal_id,
    )
    if proposal is None:
        raise HTTPException(status_code=404, detail="trade proposal not found")
    return proposal


@router.post(
    "/trade-proposals/{proposal_id}/order-review",
    status_code=status.HTTP_201_CREATED,
)
async def review_trade_order(
    proposal_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.executions.review(
            user_id=principal.user_id,
            proposal_id=proposal_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="trade proposal not found") from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/trade-proposals/{proposal_id}/submit",
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_trade_order(
    proposal_id: UUID,
    payload: SubmitOrderInput,
    principal: Annotated[Principal, Depends(require_execution_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.executions.submit(
            user_id=principal.user_id,
            proposal_id=proposal_id,
            payload=payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="trade proposal not found") from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/orders/{order_id}")
async def get_order(
    order_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    order = await studio.executions.get_order(user_id=principal.user_id, order_id=order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return order


@router.get("/orders")
async def list_orders(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    proposal_id: UUID | None = None,
):
    return await studio.executions.list_orders(
        user_id=principal.user_id, limit=limit, offset=offset, proposal_id=proposal_id
    )


@router.post("/orders/{order_id}/cancel-review", status_code=status.HTTP_201_CREATED)
async def review_order_cancellation(
    order_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.executions.review_cancel_order(
            user_id=principal.user_id, order_id=order_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="order not found") from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/orders/{order_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def confirm_order_cancellation(
    order_id: UUID,
    payload: ConfirmExecutionActionInput,
    principal: Annotated[Principal, Depends(require_execution_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.executions.cancel_order(
            user_id=principal.user_id,
            order_id=order_id,
            payload=payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="order or review not found") from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/positions")
async def list_positions(
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
    open_only: bool = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    connection_id: UUID | None = None,
):
    return await studio.executions.list_positions(
        user_id=principal.user_id,
        open_only=open_only,
        connection_id=connection_id,
        limit=limit,
        offset=offset,
    )


@router.get("/positions/{position_id}")
async def get_position(
    position_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    position = await studio.executions.get_position(
        user_id=principal.user_id, position_id=position_id
    )
    if position is None:
        raise HTTPException(status_code=404, detail="position not found")
    return position


@router.post("/positions/{position_id}/close-review", status_code=status.HTTP_201_CREATED)
async def review_position_close(
    position_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.executions.review_close_position(
            user_id=principal.user_id, position_id=position_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="position not found") from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/positions/{position_id}/close", status_code=status.HTTP_202_ACCEPTED)
async def confirm_position_close(
    position_id: UUID,
    payload: ConfirmExecutionActionInput,
    principal: Annotated[Principal, Depends(require_execution_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.executions.close_position(
            user_id=principal.user_id,
            position_id=position_id,
            payload=payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="position or review not found") from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/positions/{position_id}/protection-review",
    status_code=status.HTTP_201_CREATED,
)
async def review_position_protection(
    position_id: UUID,
    payload: UpdateProtectionInput,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.executions.review_position_protection(
            user_id=principal.user_id,
            position_id=position_id,
            payload=payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="position not found") from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/positions/{position_id}/protection", status_code=status.HTTP_202_ACCEPTED)
async def confirm_position_protection(
    position_id: UUID,
    payload: ConfirmExecutionActionInput,
    principal: Annotated[Principal, Depends(require_execution_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.executions.update_position_protection(
            user_id=principal.user_id,
            position_id=position_id,
            payload=payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="position or review not found") from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/execution-actions/{action_id}")
async def get_execution_action(
    action_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    action = await studio.executions.get_action(user_id=principal.user_id, action_id=action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="execution action not found")
    return action


@router.post("/trade-proposals/{proposal_id}/reject")
async def reject_trade_proposal(
    proposal_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
):
    try:
        return await studio.proposals.reject(user_id=principal.user_id, proposal_id=proposal_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="trade proposal not found") from exc
    except ProposalConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/trade-proposals/{proposal_id}/feedback", status_code=204)
async def add_trade_proposal_feedback(
    proposal_id: UUID,
    payload: ProposalFeedback,
    principal: Annotated[Principal, Depends(require_principal)],
    studio: Annotated[StudioServices, Depends(get_studio)],
) -> Response:
    try:
        await studio.proposals.add_feedback(
            user_id=principal.user_id,
            proposal_id=proposal_id,
            payload=payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="trade proposal not found") from exc
    return Response(status_code=204)
