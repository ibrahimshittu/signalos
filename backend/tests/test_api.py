from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from signalos_backend.config import Settings
from signalos_backend.domain import ClaimKind, EvidenceClaim, SourceTier
from signalos_backend.main import create_app

USER_HEADERS = {"X-SignalOS-User-Id": "user-a"}


def test_fast_question_publishes_cited_report(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        api_key="test-key",
        logfire_send=False,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        graph = app.state.service.evidence
        source = graph.ingest_source(
            provider="Federal Reserve",
            uri="https://federalreserve.gov/example",
            title="Policy statement",
            tier=SourceTier.TIER_1,
            content="The target rate was held unchanged.",
            published_at=datetime.now(UTC),
        )
        graph.verify_source(source.id)
        claim = graph.propose_claim(
            EvidenceClaim(
                text="The target rate was held unchanged.",
                kind=ClaimKind.VERIFIED_FACT,
                entity_ids=("rates",),
                source_ids=(source.id,),
                authority_score=Decimal("1"),
                independence_score=Decimal("0.9"),
                completeness_score=Decimal("1"),
            )
        )
        graph.admit_claim(claim.id)
        response = client.post(
            "/v1/intelligence/questions",
            headers=USER_HEADERS,
            json={
                "question": "What happened to rates?",
                "context_entity_ids": ["rates"],
                "mode": "fast",
            },
        )
        assert response.status_code == 202
        run = response.json()
        assert run["status"] == "published"
        report = client.get(
            f"/v1/intelligence/reports/{run['report_id']}", headers=USER_HEADERS
        ).json()
        assert report["citations"][0]["source_id"] == str(source.id)
        events = client.get(
            f"/v1/intelligence/questions/{run['id']}/events", headers=USER_HEADERS
        ).json()
        assert [event["sequence"] for event in events] == [0, 1, 2, 3, 4]


def test_admin_endpoints_are_protected(tmp_path):
    app = create_app(
        Settings(environment="test", database_url=f"sqlite+aiosqlite:///{tmp_path / 'admin.db'}")
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/admin/evidence/sources",
            json={
                "provider": "SEC",
                "uri": "https://sec.gov",
                "title": "SEC source",
                "tier": 1,
                "content": "data",
            },
        )
        assert response.status_code == 403


def test_strategy_admission_requires_evaluation_before_validation(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'admission.db'}",
        api_key="operator",
    )
    path = "/v1/admin/strategies/managed-trend-filter/1.0.0/transition"
    headers = {"X-SignalOS-Admin-Key": "operator"}
    with TestClient(create_app(settings)) as client:
        assert client.post(path, params={"target": "research"}, headers=headers).status_code == 200
        blocked = client.post(path, params={"target": "validated"}, headers=headers)
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == "passing version-bound evaluation required"


def test_persisted_evidence_survives_restart_and_run_is_idempotent(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'durable.db'}"
    settings = Settings(
        environment="test",
        database_url=database_url,
        api_key="operator",
    )
    headers = {"X-SignalOS-Admin-Key": "operator"}
    with TestClient(create_app(settings)) as client:
        source_response = client.post(
            "/v1/admin/evidence/sources",
            headers=headers,
            json={
                "provider": "SEC",
                "uri": "https://sec.gov/filing",
                "title": "Company filing",
                "tier": 1,
                "content": "The company reported positive operating cash flow.",
                "published_at": datetime.now(UTC).isoformat(),
            },
        )
        source_id = source_response.json()["id"]
        client.post(f"/v1/admin/evidence/sources/{source_id}/verify", headers=headers)
        claim_response = client.post(
            "/v1/admin/evidence/claims",
            headers=headers,
            json={
                "text": "The company reported positive operating cash flow.",
                "kind": "verified_fact",
                "entity_ids": ["company"],
                "source_ids": [source_id],
                "freshness_class": "quarterly",
                "authority_score": "1",
                "independence_score": "0.8",
                "completeness_score": "0.9",
            },
        )
        claim_id = claim_response.json()["id"]
        assert (
            client.post(f"/v1/admin/evidence/claims/{claim_id}/admit", headers=headers).status_code
            == 200
        )

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/intelligence/questions",
            headers=USER_HEADERS,
            json={
                "question": "What did the company report?",
                "context_entity_ids": ["company"],
                "mode": "fast",
            },
        )
        run = response.json()
        first_report_id = run["report_id"]
        repeated = client.post(
            f"/v1/intelligence/runs/{run['id']}/execute",
            headers=headers,
        ).json()
        assert repeated["report_id"] == first_report_id
        events = client.get(
            f"/v1/intelligence/questions/{run['id']}/events", headers=USER_HEADERS
        ).json()
        assert len(events) == 5


def test_intelligence_runs_and_reports_are_user_isolated(tmp_path):
    app = create_app(
        Settings(environment="test", database_url=f"sqlite+aiosqlite:///{tmp_path / 'tenant.db'}")
    )
    with TestClient(app) as client:
        created = client.post(
            "/v1/intelligence/questions",
            headers=USER_HEADERS,
            json={"question": "What is the current evidence?", "mode": "fast"},
        ).json()
        other = {"X-SignalOS-User-Id": "user-b"}

        assert (
            client.get(f"/v1/intelligence/questions/{created['id']}", headers=other).status_code
            == 404
        )
        assert (
            client.get(
                f"/v1/intelligence/reports/{created['report_id']}", headers=other
            ).status_code
            == 404
        )
