from signalos_backend.intelligence.agents import build_deferred_capabilities, build_research_harness
from signalos_backend.seeds import build_skill_registry


def test_specialist_capabilities_are_deferred_and_stably_identified():
    capabilities = build_deferred_capabilities(build_skill_registry())
    assert len(capabilities) == 14
    assert all(capability.defer_loading for capability in capabilities)
    assert {capability.id for capability in capabilities} >= {
        "source-verification",
        "risk-management",
        "company-fundamentals",
    }


def test_research_install_exposes_one_sandboxed_code_mode_capability():
    capabilities = build_research_harness()
    assert len(capabilities) == 1
    assert capabilities[0].max_retries == 2
