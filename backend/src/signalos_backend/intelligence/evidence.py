from __future__ import annotations

import hashlib
import html
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from signalos_backend.domain import (
    ClaimKind,
    EvidenceClaim,
    EvidenceEdge,
    EvidenceRelation,
    EvidenceSource,
    SourceTier,
)

_SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_PROMPT_INJECTION = re.compile(
    r"(?im)^\s*(system|assistant|developer)\s*:|ignore\s+(all\s+)?previous\s+instructions|"
    r"reveal\s+(the\s+)?system\s+prompt|call\s+the\s+tool|override\s+(your\s+)?policy"
)
_WHITESPACE = re.compile(r"\s+")


def sanitize_external_text(raw: str, *, max_chars: int = 100_000) -> str:
    """Treat retrieved content as data and strip executable/prompt-like material."""
    cleaned = _SCRIPT.sub(" ", raw[:max_chars])
    cleaned = _STYLE.sub(" ", cleaned)
    cleaned = _TAGS.sub(" ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = _PROMPT_INJECTION.sub("[removed untrusted instruction]", cleaned)
    return _WHITESPACE.sub(" ", cleaned).strip()


def fingerprint_text(text: str) -> str:
    normalized = _WHITESPACE.sub(" ", text).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _freshness_limit(freshness_class: str) -> timedelta:
    return {
        "realtime": timedelta(minutes=15),
        "daily": timedelta(days=2),
        "quarterly": timedelta(days=120),
        "structural": timedelta(days=730),
    }[freshness_class]


@dataclass
class EvidenceGraph:
    sources: dict[UUID, EvidenceSource] = field(default_factory=dict)
    claims: dict[UUID, EvidenceClaim] = field(default_factory=dict)
    edges: list[EvidenceEdge] = field(default_factory=list)
    _fingerprints: dict[str, UUID] = field(default_factory=dict)

    def restore(self, sources: list[EvidenceSource], claims: list[EvidenceClaim]) -> None:
        """Reconstruct the graph from durable source-of-truth records on process restart."""
        self.sources = {source.id: source for source in sources}
        self.claims = {claim.id: claim for claim in claims}
        self._fingerprints = {source.fingerprint: source.id for source in sources}

    def ingest_source(
        self,
        *,
        provider: str,
        uri: str,
        title: str,
        tier: SourceTier,
        content: str,
        published_at: datetime | None = None,
    ) -> EvidenceSource:
        sanitized = sanitize_external_text(content)
        fingerprint = fingerprint_text(sanitized)
        if fingerprint in self._fingerprints:
            return self.sources[self._fingerprints[fingerprint]]
        source = EvidenceSource(
            provider=provider,
            uri=uri,
            title=title,
            tier=tier,
            published_at=published_at,
            fingerprint=fingerprint,
            content_excerpt=sanitized[:2_000],
        )
        self.sources[source.id] = source
        self._fingerprints[fingerprint] = source.id
        return source

    def verify_source(self, source_id: UUID) -> EvidenceSource:
        source = self.sources[source_id]
        verified = source.model_copy(update={"quarantined": False, "verified": True})
        self.sources[source_id] = verified
        return verified

    def propose_claim(self, claim: EvidenceClaim) -> EvidenceClaim:
        missing = set(claim.source_ids) - self.sources.keys()
        if missing:
            raise ValueError(f"unknown source IDs: {sorted(map(str, missing))}")
        if claim.kind is ClaimKind.VERIFIED_FACT and any(
            self.sources[source_id].tier is SourceTier.TIER_4 for source_id in claim.source_ids
        ):
            raise ValueError("Tier 4 sources cannot establish verified facts")
        self.claims[claim.id] = claim
        return claim

    def admit_claim(self, claim_id: UUID, *, now: datetime | None = None) -> EvidenceClaim:
        now = now or datetime.now(UTC)
        claim = self.claims[claim_id]
        sources = [self.sources[source_id] for source_id in claim.source_ids]
        if not all(source.verified for source in sources):
            raise ValueError("all sources must be verified before claim admission")
        if claim.kind is ClaimKind.VERIFIED_FACT:
            providers = {source.provider.lower() for source in sources}
            has_primary = any(source.tier is SourceTier.TIER_1 for source in sources)
            if not has_primary and len(providers) < 2:
                raise ValueError("fact requires a Tier 1 source or two independent providers")
        timestamps = [source.published_at or source.retrieved_at for source in sources]
        if timestamps and now - max(timestamps) > _freshness_limit(claim.freshness_class):
            raise ValueError("evidence is stale for this claim")
        admitted = claim.model_copy(update={"admitted": True})
        self.claims[claim_id] = admitted
        return admitted

    def relate(self, from_id: UUID, to_id: UUID, relation: EvidenceRelation) -> EvidenceEdge:
        known = set(self.claims) | set(self.sources)
        if from_id not in known or to_id not in known:
            raise ValueError("edge endpoint not found")
        edge = EvidenceEdge(from_id=from_id, to_id=to_id, relation=relation)
        self.edges.append(edge)
        return edge

    def search(self, query: str, *, entity_ids: tuple[str, ...] = ()) -> list[EvidenceClaim]:
        terms = {
            token[:-1] if token.endswith("s") else token
            for token in re.findall(r"[a-z0-9]+", query.lower())
            if token not in {"a", "an", "the", "to", "what", "why", "how", "did", "was"}
        }
        results = []
        for claim in self.claims.values():
            if not claim.admitted:
                continue
            entity_match = not entity_ids or bool(set(entity_ids) & set(claim.entity_ids))
            claim_terms = {
                token[:-1] if token.endswith("s") else token
                for token in re.findall(r"[a-z0-9]+", claim.text.lower())
            }
            text_match = not terms or bool(terms & claim_terms)
            if entity_ids and entity_match:
                text_match = True
            if entity_match and text_match:
                results.append(claim)
        return sorted(
            results,
            key=lambda item: (
                item.authority_score + item.independence_score + item.completeness_score
            ),
            reverse=True,
        )

    def quality(self, claim_ids: list[UUID]) -> Decimal:
        if not claim_ids:
            return Decimal("0")
        values = []
        for claim_id in claim_ids:
            claim = self.claims[claim_id]
            values.append(
                (claim.authority_score + claim.independence_score + claim.completeness_score)
                / Decimal("3")
            )
        return sum(values, Decimal("0")) / Decimal(len(values))

    def contradictions(self) -> dict[UUID, list[UUID]]:
        result: dict[UUID, list[UUID]] = defaultdict(list)
        for edge in self.edges:
            if edge.relation is EvidenceRelation.CONTRADICTS:
                result[edge.from_id].append(edge.to_id)
        return result
