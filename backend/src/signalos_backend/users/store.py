from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Numeric, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from signalos_backend.db import Base
from signalos_backend.users.domain import (
    InvestmentProfile,
    InvestmentProfileInput,
    PersonalizedInvestmentPolicy,
    PersonalizedPreferences,
    PersonalizedPreferencesUpdate,
)
from signalos_backend.users.mandate import derive_adaptive_mandate


class InvestmentProfileRecord(Base):
    __tablename__ = "investment_profiles"

    user_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    goals: Mapped[list[str]] = mapped_column(JSON)
    intended_capital: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    time_horizon: Mapped[str] = mapped_column(String(40))
    liquidity_need: Mapped[str] = mapped_column(String(40))
    investing_experience: Mapped[str] = mapped_column(String(40))
    trading_experience: Mapped[str] = mapped_column(String(40))
    products_traded: Mapped[list[str]] = mapped_column(JSON)
    decision_frequency: Mapped[str] = mapped_column(String(40))
    drawdown_response: Mapped[str] = mapped_column(String(40))
    holding_periods: Mapped[list[str]] = mapped_column(JSON)
    explanation_detail: Mapped[str] = mapped_column(String(40))
    notification_frequency: Mapped[str] = mapped_column(String(40))
    disclosures_accepted: Mapped[bool] = mapped_column(Boolean)
    disclosures_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PersonalizedPolicyRecord(Base):
    __tablename__ = "personalized_investment_policies"

    user_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    preferences: Mapped[dict[str, object]] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(40))
    policy_version: Mapped[str] = mapped_column(String(80))
    profile_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class UserStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def save_profile(
        self, user_id: str, profile: InvestmentProfileInput
    ) -> InvestmentProfile:
        now = datetime.now(UTC)
        async with self.sessions() as session:
            record = await session.get(InvestmentProfileRecord, user_id)
            values = {
                "goals": [item.value for item in profile.goals],
                "intended_capital": profile.intended_capital,
                "time_horizon": profile.time_horizon.value,
                "liquidity_need": profile.liquidity_need.value,
                "investing_experience": profile.investing_experience.value,
                "trading_experience": profile.trading_experience.value,
                "products_traded": [item.value for item in profile.products_traded],
                "decision_frequency": profile.decision_frequency.value,
                "drawdown_response": profile.drawdown_response.value,
                "holding_periods": [item.value for item in profile.holding_periods],
                "explanation_detail": profile.explanation_detail.value,
                "notification_frequency": profile.notification_frequency.value,
                "disclosures_accepted": profile.disclosures_accepted,
            }
            if record is None:
                record = InvestmentProfileRecord(
                    user_id=user_id,
                    disclosures_accepted_at=now if profile.disclosures_accepted else None,
                    created_at=now,
                    updated_at=now,
                    **values,
                )
                session.add(record)
            else:
                for field, value in values.items():
                    setattr(record, field, value)
                if profile.disclosures_accepted and record.disclosures_accepted_at is None:
                    record.disclosures_accepted_at = now
                if not profile.disclosures_accepted:
                    record.disclosures_accepted_at = None
                record.updated_at = now
            await session.commit()
            await session.refresh(record)
            return self._to_domain(record)

    async def get_profile(self, user_id: str) -> InvestmentProfile | None:
        async with self.sessions() as session:
            record = await session.scalar(
                select(InvestmentProfileRecord).where(InvestmentProfileRecord.user_id == user_id)
            )
            return self._to_domain(record) if record else None

    async def save_personalized_policy(
        self,
        *,
        profile: InvestmentProfile,
        preferences: PersonalizedPreferences,
        source: str,
    ) -> PersonalizedInvestmentPolicy:
        now = datetime.now(UTC)
        async with self.sessions() as session:
            record = await session.get(PersonalizedPolicyRecord, profile.user_id)
            values = {
                "preferences": preferences.model_dump(mode="json"),
                "source": source,
                "policy_version": "personalization-policy-1.0.0",
                "profile_updated_at": profile.updated_at,
                "updated_at": now,
            }
            if record is None:
                record = PersonalizedPolicyRecord(
                    user_id=profile.user_id,
                    created_at=now,
                    **values,
                )
                session.add(record)
            else:
                for field, value in values.items():
                    setattr(record, field, value)
            await session.commit()
            await session.refresh(record)
            return self._policy_to_domain(record, profile)

    async def get_personalized_policy(
        self, user_id: str
    ) -> PersonalizedInvestmentPolicy | None:
        async with self.sessions() as session:
            policy = await session.get(PersonalizedPolicyRecord, user_id)
            profile = await session.get(InvestmentProfileRecord, user_id)
            if policy is None or profile is None:
                return None
            return self._policy_to_domain(policy, self._to_domain(profile))

    async def update_personalized_policy(
        self,
        *,
        user_id: str,
        payload: PersonalizedPreferencesUpdate,
    ) -> PersonalizedInvestmentPolicy | None:
        now = datetime.now(UTC)
        async with self.sessions() as session:
            policy = await session.get(PersonalizedPolicyRecord, user_id)
            profile_record = await session.get(InvestmentProfileRecord, user_id)
            if policy is None or profile_record is None:
                return None
            current = PersonalizedPreferences.model_validate(policy.preferences)
            updates = payload.model_dump(exclude_none=True)
            policy.preferences = current.model_copy(update=updates).model_dump(mode="json")
            policy.source = "user_edited"
            policy.updated_at = now
            await session.commit()
            await session.refresh(policy)
            return self._policy_to_domain(policy, self._to_domain(profile_record))

    @staticmethod
    def _to_domain(record: InvestmentProfileRecord) -> InvestmentProfile:
        input_profile = InvestmentProfileInput(
            goals=tuple(record.goals),
            intended_capital=record.intended_capital,
            time_horizon=record.time_horizon,
            liquidity_need=record.liquidity_need,
            investing_experience=record.investing_experience,
            trading_experience=record.trading_experience,
            products_traded=tuple(record.products_traded),
            decision_frequency=record.decision_frequency,
            drawdown_response=record.drawdown_response,
            holding_periods=tuple(record.holding_periods),
            explanation_detail=record.explanation_detail,
            notification_frequency=record.notification_frequency,
            disclosures_accepted=record.disclosures_accepted,
        )
        return InvestmentProfile(
            user_id=record.user_id,
            **input_profile.model_dump(),
            disclosures_accepted_at=record.disclosures_accepted_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
            adaptive_mandate=derive_adaptive_mandate(input_profile),
        )

    @staticmethod
    def _policy_to_domain(
        record: PersonalizedPolicyRecord,
        profile: InvestmentProfile,
    ) -> PersonalizedInvestmentPolicy:
        return PersonalizedInvestmentPolicy(
            user_id=record.user_id,
            preferences=PersonalizedPreferences.model_validate(record.preferences),
            safety_mandate=profile.adaptive_mandate,
            source=record.source,
            policy_version=record.policy_version,
            profile_updated_at=record.profile_updated_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
