from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from signalos_backend.brokers.store import BrokerStore
from signalos_backend.users.domain import (
    InvestmentProfile,
    InvestmentProfileInput,
    OnboardingState,
    PersonalizedInvestmentPolicy,
    PersonalizedPreferencesUpdate,
)
from signalos_backend.users.memory import UserMemory, UserMemoryStore
from signalos_backend.users.personalization import PersonalizationGenerator
from signalos_backend.users.store import UserStore


@dataclass(frozen=True)
class UserService:
    users: UserStore
    brokers: BrokerStore
    memories: UserMemoryStore
    personalizer: PersonalizationGenerator

    async def save_profile(
        self, *, user_id: str, payload: InvestmentProfileInput
    ) -> InvestmentProfile:
        profile = await self.users.save_profile(user_id, payload)
        generated = await self.personalizer.generate(profile)
        await self.users.save_personalized_policy(
            profile=profile,
            preferences=generated.preferences,
            source=generated.source,
        )
        return profile

    async def get_profile(self, *, user_id: str) -> InvestmentProfile | None:
        return await self.users.get_profile(user_id)

    async def get_personalized_policy(
        self, *, user_id: str
    ) -> PersonalizedInvestmentPolicy | None:
        return await self.users.get_personalized_policy(user_id)

    async def generate_personalized_policy(
        self, *, user_id: str
    ) -> PersonalizedInvestmentPolicy:
        profile = await self.users.get_profile(user_id)
        if profile is None:
            raise KeyError(user_id)
        generated = await self.personalizer.generate(profile)
        return await self.users.save_personalized_policy(
            profile=profile,
            preferences=generated.preferences,
            source=generated.source,
        )

    async def update_personalized_policy(
        self,
        *,
        user_id: str,
        payload: PersonalizedPreferencesUpdate,
    ) -> PersonalizedInvestmentPolicy | None:
        return await self.users.update_personalized_policy(
            user_id=user_id,
            payload=payload,
        )

    async def onboarding_state(self, *, user_id: str) -> OnboardingState:
        profile = await self.users.get_profile(user_id)
        has_connection = await self.brokers.has_healthy_read_connection(user_id)
        context = await self.brokers.get_context(user_id=user_id)
        connection = (
            await self.brokers.get_connection(user_id=user_id, connection_id=context.connection_id)
            if context is not None else None
        )
        profile_completed = profile is not None
        disclosures = bool(profile and profile.disclosures_accepted)
        missing: list[str] = []
        if not profile_completed:
            missing.append("investment_profile")
        if not disclosures:
            missing.append("disclosures")
        if not has_connection:
            missing.extend(("broker_account_read_connection", "initial_account_sync"))
        return OnboardingState(
            investment_profile_completed=profile_completed,
            disclosures_accepted=disclosures,
            broker_account_read_connected=has_connection,
            initial_account_sync_completed=has_connection,
            studio_unlocked=not missing,
            missing_requirements=tuple(missing),
            investment_profile=profile,
            broker_connection=connection,
        )

    async def list_memories(
        self, *, user_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[UserMemory, ...]:
        return await self.memories.list(user_id=user_id, limit=limit, offset=offset)

    async def delete_memory(self, *, user_id: str, memory_id: UUID) -> bool:
        return await self.memories.delete(user_id=user_id, memory_id=memory_id)

    async def reset_learned_preferences(self, *, user_id: str) -> None:
        await self.memories.reset_learned_preferences(user_id=user_id)
