from __future__ import annotations

from dataclasses import dataclass

from signalos_backend.brokers.context import BrokerContextService
from signalos_backend.brokers.service import BrokerService
from signalos_backend.execution.service import ExecutionService
from signalos_backend.market.service import MarketService
from signalos_backend.notifications.service import NotificationService
from signalos_backend.proposals.service import ProposalService
from signalos_backend.users.service import UserService


@dataclass(frozen=True)
class StudioServices:
    users: UserService
    brokers: BrokerService
    broker_contexts: BrokerContextService
    markets: MarketService
    proposals: ProposalService
    executions: ExecutionService
    notifications: NotificationService
