from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from typing import Protocol

from signalos_backend.domain import (
    SkillManifest,
    SkillStatus,
    StrategySpec,
    StrategyStatus,
    ToolManifest,
)


class Versioned(Protocol):
    version: str


def _semver(value: str) -> tuple[int, int, int]:
    major, minor, patch = value.split(".")
    return int(major), int(minor), int(patch)


class VersionedRegistry[T: Versioned]:
    """Thread-safe append-only registry; versions are never overwritten."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, T]] = {}
        self._lock = RLock()

    def add(self, stable_id: str, item: T) -> T:
        with self._lock:
            versions = self._items.setdefault(stable_id, {})
            if item.version in versions:
                raise ValueError(f"{stable_id}@{item.version} already exists")
            versions[item.version] = item
        return item

    def restore(self, stable_id: str, item: T) -> T:
        """Load a trusted durable record, replacing the same version from static seeds."""
        with self._lock:
            self._items.setdefault(stable_id, {})[item.version] = item
        return item

    def get(self, stable_id: str, version: str | None = None) -> T:
        versions = self._items.get(stable_id)
        if not versions:
            raise KeyError(stable_id)
        selected = version or max(versions, key=_semver)
        return versions[selected]

    def list_latest(self) -> list[T]:
        return [self.get(stable_id) for stable_id in sorted(self._items)]

    def versions(self, stable_id: str) -> list[T]:
        versions = self._items.get(stable_id, {})
        return [versions[key] for key in sorted(versions, key=_semver)]


_ALLOWED_STRATEGY_TRANSITIONS: dict[StrategyStatus, set[StrategyStatus]] = {
    StrategyStatus.DISCOVERED: {StrategyStatus.QUARANTINED},
    StrategyStatus.QUARANTINED: {StrategyStatus.RESEARCH, StrategyStatus.RETIRED},
    StrategyStatus.RESEARCH: {StrategyStatus.VALIDATED, StrategyStatus.BENCHED},
    StrategyStatus.VALIDATED: {StrategyStatus.SHADOW, StrategyStatus.BENCHED},
    StrategyStatus.SHADOW: {StrategyStatus.PROMOTION_PENDING, StrategyStatus.BENCHED},
    StrategyStatus.PROMOTION_PENDING: {StrategyStatus.APPROVED, StrategyStatus.BENCHED},
    StrategyStatus.APPROVED: {StrategyStatus.BENCHED, StrategyStatus.RETIRED},
    StrategyStatus.BENCHED: {StrategyStatus.RESEARCH, StrategyStatus.RETIRED},
    StrategyStatus.RETIRED: set(),
}


class StrategyRegistry(VersionedRegistry[StrategySpec]):
    def register_candidate(self, spec: StrategySpec) -> StrategySpec:
        if spec.status not in {StrategyStatus.DISCOVERED, StrategyStatus.QUARANTINED}:
            raise ValueError("agent-created strategies must enter discovered or quarantined")
        return self.add(spec.id, spec)

    def transition(
        self,
        strategy_id: str,
        version: str,
        target: StrategyStatus,
        *,
        operator_approved: bool = False,
    ) -> StrategySpec:
        current = self.get(strategy_id, version)
        if target not in _ALLOWED_STRATEGY_TRANSITIONS[current.status]:
            raise ValueError(f"invalid transition {current.status} -> {target}")
        if target is StrategyStatus.APPROVED and not operator_approved:
            raise PermissionError("operator approval is required")
        updated = current.model_copy(update={"status": target})
        with self._lock:
            self._items[strategy_id][version] = updated
        return updated

    def approved(self) -> list[StrategySpec]:
        return [item for item in self.list_latest() if item.status is StrategyStatus.APPROVED]


class SkillRegistry(VersionedRegistry[SkillManifest]):
    def register_candidate(self, manifest: SkillManifest) -> SkillManifest:
        if manifest.status is not SkillStatus.QUARANTINED:
            raise ValueError("new skills must be quarantined")
        missing = [skill for skill in manifest.required_skills if skill not in self._items]
        if missing:
            raise ValueError(f"required skills are missing: {missing}")
        return self.add(manifest.stable_id, manifest)

    def promote(self, stable_id: str, version: str, *, operator_approved: bool) -> SkillManifest:
        if not operator_approved:
            raise PermissionError("operator approval is required")
        current = self.get(stable_id, version)
        if current.status not in {SkillStatus.QUARANTINED, SkillStatus.VALIDATED}:
            raise ValueError(f"cannot promote skill in {current.status}")
        updated = current.model_copy(update={"status": SkillStatus.APPROVED})
        with self._lock:
            self._items[stable_id][version] = updated
        return updated


class ToolRegistry:
    def __init__(self, tools: Iterable[ToolManifest] = ()) -> None:
        self._tools: dict[str, ToolManifest] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: ToolManifest) -> ToolManifest:
        if tool.stable_id in self._tools:
            raise ValueError(f"tool {tool.stable_id} already exists")
        self._tools[tool.stable_id] = tool
        return tool

    def get(self, stable_id: str, *, agent: str | None = None) -> ToolManifest:
        tool = self._tools[stable_id]
        if agent is not None and agent not in tool.allowed_agents:
            raise PermissionError(f"{agent} cannot use {stable_id}")
        return tool

    def search(self, query: str, *, agent: str, code_mode: bool = False) -> list[ToolManifest]:
        terms = set(query.lower().split())
        matches = []
        for tool in self._tools.values():
            if agent not in tool.allowed_agents or (code_mode and not tool.code_mode):
                continue
            haystack = f"{tool.stable_id} {tool.purpose}".lower()
            if not terms or any(term in haystack for term in terms):
                matches.append(tool)
        return sorted(matches, key=lambda item: item.stable_id)

    def public(self) -> list[ToolManifest]:
        return sorted(self._tools.values(), key=lambda item: item.stable_id)
