"""
Unit and Integration Tests for GraphRAG Subsystem.
Tests anti-leakage quarantine boundaries, policy retrieval, typology retrieval,
provenance tracking, context budget control, and workflow integration.
"""

import pytest
from pathlib import Path

from src.rag.sources import (
    validate_path_allowed,
    is_path_excluded,
    get_authoritative_sources,
    EXCLUDED_PATTERNS,
    REPO_ROOT
)
from src.rag.provenance import ProvenanceItem, ProvenanceType
from src.rag.chunker import PolicyChunker, DocumentChunk
from src.rag.retriever import PolicyRetriever, get_policy_retriever
from src.rag.context_builder import GraphRAGContextBuilder
from src.agent.state import InvestigationState, CaseStatus
from src.agent.workflow import InvestigationWorkflow
from src.agent.tools.contracts import InvestigationTools
from src.agent.llm.mock import MockLLMProvider
from src.graph.adapter import GraphAdapter


class TestAntiLeakageQuarantine:
    """Ensures no benchmark answers or ground truth files can ever leak into RAG."""

    def test_quarantined_files_flagged(self):
        quarantined = [
            "docs/manual_case_investigation.md",
            "docs/hhg001_verification.md",
            "docs/hhg014_graph_verification.md",
            "docs/benchmark_coverage_audit.md",
            "docs/real_llm_smoketest.md",
            "cases/case_pack.csv",
            "cases/hhg001.json",
            "results/answers.json",
            "docs/audit_results_cache.json"
        ]
        for path in quarantined:
            assert is_path_excluded(path) is True, f"Path {path} should be flagged as excluded"
            with pytest.raises(ValueError, match="Security Leakage Violation"):
                validate_path_allowed(path)

    def test_authoritative_sources_pass_validation(self):
        sources = get_authoritative_sources()
        assert len(sources) >= 2
        for s in sources:
            assert is_path_excluded(str(s)) is False


class TestPolicyAndTypologyRetrieval:
    """Verifies BM25 / keyword retrieval accuracy across policy rules and typologies."""

    @pytest.fixture
    def retriever(self):
        return get_policy_retriever()

    def test_weak_signal_retrieves_rule_r1(self, retriever):
        results = retriever.retrieve_policies("weak single signal low probability verification", top_k=2)
        assert len(results) > 0
        prov_ids = [r.provenance_id for r in results]
        assert "POLICY-R1" in prov_ids

    def test_customer_denied_retrieves_rule_r2(self, retriever):
        results = retriever.retrieve_policies("customer denied transaction unauthorized charge", top_k=2)
        assert len(results) > 0
        prov_ids = [r.provenance_id for r in results]
        assert "POLICY-R2" in prov_ids

    def test_customer_confirmed_retrieves_rule_r3(self, retriever):
        results = retriever.retrieve_policies("customer confirms legitimate travel purchase routine", top_k=2)
        assert len(results) > 0
        prov_ids = [r.provenance_id for r in results]
        assert "POLICY-R3" in prov_ids

    def test_shared_device_retrieves_rule_r6(self, retriever):
        results = retriever.retrieve_policies("shared device profile syndicate multi-card cluster", top_k=2)
        assert len(results) > 0
        prov_ids = [r.provenance_id for r in results]
        assert "POLICY-R6" in prov_ids

    def test_sar_criteria_retrieval(self, retriever):
        results = retriever.retrieve_policies("fincen sar file report regulatory threshold 1000", top_k=2)
        assert len(results) > 0
        prov_ids = [r.provenance_id for r in results]
        assert any("SAR" in pid or "R2" in pid or "R6" in pid for pid in prov_ids)

    def test_card_testing_typology_retrieval(self, retriever):
        results = retriever.retrieve_typologies("multiple rapid small authorizations under 5 dollars", top_k=2)
        assert len(results) > 0
        prov_ids = [r.provenance_id for r in results]
        assert "TYPOLOGY-CARD-TESTING" in prov_ids

    def test_out_of_region_typology_retrieval(self, retriever):
        results = retriever.retrieve_typologies("foreign novel billing region out of region card present", top_k=2)
        assert len(results) > 0
        prov_ids = [r.provenance_id for r in results]
        assert "TYPOLOGY-OUT-OF-REGION" in prov_ids


class TestGraphRAGContextBuilder:
    """Verifies context assembly, bounding, and provenance traceability."""

    def test_context_builder_structures_provenance(self):
        state = InvestigationState(
            case_id="TEST-001",
            trigger_type="risk_score",
            trigger_text="Elevated score 0.88",
            flagged_txn_id="TXN-9999",
            card_id="CARD-1234",
            customer_id="CUST-5678",
            billing_regions=["BR-99"]
        )
        state.transaction_context = {
            "transaction": {
                "amount": 250.0,
                "risk_score": 0.88,
                "channel": "online",
                "device_os": "iOS",
                "device_browser": "Mobile Safari",
                "is_proxy": False
            }
        }
        state.card_history_summary = {
            "total_transactions": 25,
            "amount_stats": {"mean_usd": 45.0, "stdev_usd": 12.0},
            "regional_summary": {"flagged_region_familiarity": "novel_zero_history", "flagged_region_txns_count": 0}
        }
        state.device_evidence = {
            "connected_card_count": 12,
            "is_shared_device": True,
            "syndicate_risk_tier": "HIGH"
        }
        state.prior_case_evidence = [
            {"case_id": "CC-0042", "incident_type": "fraud", "outcome": "confirmed", "incident_description": "Shared device ring across 15 accounts"}
        ]

        builder = GraphRAGContextBuilder(token_budget=2500)
        context = builder.build_context(state)

        # 1. Structure assertions
        assert "graph_evidence" in context
        assert "case_memory" in context
        assert "retrieved_policies" in context
        assert "retrieved_typologies" in context
        assert "provenance_map" in context
        assert "rendered_prompt_context" in context

        # 2. Provenance IDs present
        prompt = context["rendered_prompt_context"]
        assert "GRAPH-TXN-TXN-9999" in prompt
        assert "GRAPH-CARD-CARD-1234" in prompt
        assert "GRAPH-DEV-" in prompt
        assert "CASE-CC-0042" in prompt
        assert "POLICY-" in prompt

        # 3. Context budget sanity check (well within token bounds)
        word_count = len(prompt.split())
        assert word_count < 2500, f"Prompt is too long: {word_count} words"


class TestWorkflowWithGraphRAG:
    """Verifies end-to-end workflow execution with GraphRAG enabled."""

    def test_workflow_populates_rag_context(self):
        adapter = GraphAdapter(backend="in_memory")
        tools = InvestigationTools(adapter=adapter)
        mock_llm = MockLLMProvider()
        workflow = InvestigationWorkflow(tools=tools, llm_provider=mock_llm)

        case_input = {
            "case_id": "HHG-001",
            "trigger_type": "risk_score",
            "trigger_text": "Model anomaly score 0.78",
            "flagged_txn_id": "2987000",
            "card_id": "card_2987000",
            "customer_id": "cust_2987000"
        }
        state = workflow.run(case_input)

        assert state.case_status == CaseStatus.COMPLETED
        assert state.rag_context is not None
        assert "retrieved_policies" in state.rag_context
        assert len(state.rag_context["retrieved_policies"]) > 0
        assert "retrieved_typologies" in state.rag_context
        assert len(state.rag_context["retrieved_typologies"]) > 0
