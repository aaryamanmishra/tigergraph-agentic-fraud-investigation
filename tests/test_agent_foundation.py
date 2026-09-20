"""
Unit and Integration Tests for Phase 3A: Agent Foundation and Tool Contracts.
Tests state initialization, state transitions, tool input/output contracts,
large-history summarization (HHG-011, HHG-018), fact/derived/inference separation,
stop conditions, and timeline events without requiring an LLM API key.
"""

import pytest
from src.agent.state import (
    InvestigationState,
    EvidenceCategory,
    EvidenceItem,
    TimelineEvent,
    CaseStatus,
    StopReason
)
from src.agent.tools.contracts import InvestigationTools, ToolExecutionResult
from src.agent.tools.summary import EvidenceSummarizer
from src.agent.nodes import InvestigationNodes
from src.agent.workflow import InvestigationWorkflow
from src.graph.adapter import GraphAdapter


@pytest.fixture
def mock_tools():
    """Provides an InvestigationTools instance backed by the local in-memory store."""
    adapter = GraphAdapter(backend="in_memory")
    return InvestigationTools(adapter=adapter)


@pytest.fixture
def workflow(mock_tools):
    """Provides a deterministic InvestigationWorkflow instance."""
    return InvestigationWorkflow(tools=mock_tools)


class TestAgentState:
    """Tests for InvestigationState and evidence categorization."""

    def test_state_initialization(self):
        state = InvestigationState(
            case_id="HHG-001",
            trigger_type="risk_score",
            trigger_text="Scored at 0.61",
            flagged_txn_id="3514030",
            card_id="C12382-K1",
            customer_id="C12382"
        )
        assert state.case_id == "HHG-001"
        assert state.case_status == CaseStatus.INITIALIZED
        assert state.stop_reason is None
        assert len(state.facts) == 0
        assert len(state.derived) == 0
        assert len(state.inferences) == 0

    def test_fact_derived_inference_separation(self):
        state = InvestigationState(case_id="HHG-001")

        # Add Fact
        fact = state.add_fact(
            source="test_source",
            description="Transaction 3514030 amount is $77.07",
            data={"amount": 77.07}
        )
        assert fact.category == EvidenceCategory.FACT
        assert len(state.facts) == 1

        # Add Derived
        derived = state.add_derived(
            source="test_source",
            description="Baseline spending mean is $77.02",
            data={"mean": 77.02}
        )
        assert derived.category == EvidenceCategory.DERIVED
        assert len(state.derived) == 1

        # Add Inference
        inference = state.add_inference(
            source="test_reasoner",
            description="Transaction likely represents routine personal travel",
            confidence=0.92
        )
        assert inference.category == EvidenceCategory.INFERENCE
        assert len(state.inferences) == 1

        # Verify strict separation in exported dictionary
        d = state.to_dict()
        assert len(d["evidence"]["facts"]) == 1
        assert d["evidence"]["facts"][0]["category"] == "FACT"
        assert len(d["evidence"]["derived"]) == 1
        assert d["evidence"]["derived"][0]["category"] == "DERIVED"
        assert len(d["evidence"]["inferences"]) == 1
        assert d["evidence"]["inferences"][0]["category"] == "INFERENCE"

    def test_timeline_event_recording(self):
        state = InvestigationState(case_id="HHG-001")
        event = state.append_timeline_event(
            stage="investigate_transaction",
            tool_used="get_transaction_context",
            evidence_discovered="Retrieved context for txn 3514030",
            result="SUCCESS",
            state_change="card_id -> C12382-K1"
        )
        assert len(state.investigation_timeline) == 1
        assert event.stage == "investigate_transaction"
        assert event.tool_used == "get_transaction_context"
        assert event.result == "SUCCESS"


class TestToolContracts:
    """Tests for typed tool contracts, input validation, and error handling."""

    def test_get_transaction_context_valid(self, mock_tools):
        res = mock_tools.get_transaction_context("3514030")
        assert isinstance(res, ToolExecutionResult)
        assert res.success is True
        assert res.data["found"] is True
        assert res.data["txn_id"] == "3514030"
        assert res.data["customer_id"] == "C12382"
        assert res.data["card"]["card_id"] == "C12382-K1"

    def test_get_transaction_context_empty_input_validation(self, mock_tools):
        res = mock_tools.get_transaction_context("")
        assert res.success is False
        assert "Transaction ID cannot be empty" in str(res.error)

    def test_get_card_history_valid(self, mock_tools):
        res = mock_tools.get_card_history("C12382-K1", summarize=True)
        assert res.success is True
        assert res.data["summary_mode"] is True
        assert res.data["card_id"] == "C12382-K1"
        assert "summary" in res.data
        assert res.data["summary"]["total_transactions"] == 422

    def test_get_card_history_empty_input_validation(self, mock_tools):
        res = mock_tools.get_card_history("")
        assert res.success is False
        assert "Card ID cannot be empty" in str(res.error)

    def test_get_customer_history_valid(self, mock_tools):
        res = mock_tools.get_customer_history("C12382", summarize=True)
        assert res.success is True
        assert res.data["customer_id"] == "C12382"
        assert "summary" in res.data
        assert res.data["summary"]["total_cards_owned"] >= 1

    def test_get_connected_cards_valid(self, mock_tools):
        res = mock_tools.get_connected_cards("C13487-K1")
        assert res.success is True
        assert res.data["card_id"] == "C13487-K1"
        assert "connected_cards" in res.data

    def test_get_similar_closed_cases_valid(self, mock_tools):
        res = mock_tools.get_similar_closed_cases(card_id="C12382-K1")
        assert res.success is True
        assert res.data["card_id"] == "C12382-K1"
        assert res.data["total_similar_cases"] == 4

    def test_detect_card_testing_valid(self, mock_tools):
        res = mock_tools.detect_card_testing("C12382-K1", "2016-12-04 19:00:00")
        assert res.success is True
        assert "is_testing" in res.data

    def test_write_case_validation(self, mock_tools):
        res = mock_tools.write_case({"case_id": ""})
        assert res.success is False
        assert "case_id is required" in str(res.error)


class TestContextSizeControl:
    """Tests for large-history summarization and token reduction (Requirement #5)."""

    def test_card_history_summarizer_metrics(self):
        sample_txns = [
            {"txn_id": "T1", "ts": "2016-10-01 12:00:00", "amount": 10.0, "billing_region": "100.0", "channel": "in_person", "risk_score": 0.1},
            {"txn_id": "T2", "ts": "2016-10-02 21:00:00", "amount": 20.0, "billing_region": "100.0", "channel": "in_person", "risk_score": 0.2},
            {"txn_id": "T3", "ts": "2016-10-08 22:00:00", "amount": 70.0, "billing_region": "444.0", "channel": "in_person", "risk_score": 0.6},
            {"txn_id": "T4", "ts": "2016-10-15 23:00:00", "amount": 75.0, "billing_region": "444.0", "channel": "in_person", "risk_score": 0.5},
            {"txn_id": "T5", "ts": "2016-10-22 22:30:00", "amount": 72.0, "billing_region": "444.0", "channel": "in_person", "risk_score": 0.5},
        ]
        summary = EvidenceSummarizer.summarize_card_history(
            txns=sample_txns,
            flagged_txn_id="T5",
            flagged_region="444.0"
        )
        assert summary["total_transactions"] == 5
        assert summary["amount_stats"]["min_usd"] == 10.0
        assert summary["amount_stats"]["max_usd"] == 75.0
        assert summary["amount_stats"]["mean_usd"] == 49.4
        assert summary["regional_summary"]["flagged_region_txns_count"] == 3
        assert len(summary["representative_sample"]) <= 12

    def test_hhg011_large_history_summarization(self, mock_tools):
        """Card C11923-K2 in HHG-011 contains 10,361 transactions."""
        res = mock_tools.get_card_history("C11923-K2", summarize=True)
        assert res.success is True
        summary = res.data["summary"]
        assert summary["total_transactions"] == 10361
        assert "mean_usd" in summary["amount_stats"]
        assert "stdev_usd" in summary["amount_stats"]
        # The representative sample is strictly capped (e.g. <= 12 items)
        assert len(summary["representative_sample"]) <= 12

    def test_hhg018_large_history_summarization(self, mock_tools):
        """Card C02354-K2 in HHG-018 contains 7,091 transactions."""
        res = mock_tools.get_card_history("C02354-K2", summarize=True)
        assert res.success is True
        summary = res.data["summary"]
        assert summary["total_transactions"] == 7091
        assert len(summary["representative_sample"]) <= 12


class TestWorkflowAndLifecycle:
    """Tests end-to-end deterministic agent workflow execution and state flow."""

    def test_hhg001_workflow_execution(self, workflow):
        case_input = {
            "case_id": "HHG-001",
            "trigger_type": "risk_score",
            "trigger_text": "Real-time model scored transaction 3514030 ($77.07, in billing region 444.0) at 0.61.",
            "flagged_txn_id": "3514030",
            "card_id": "C12382-K1",
            "customer_id": "C12382"
        }
        final_state = workflow.run(case_input)

        assert final_state.case_status == CaseStatus.COMPLETED
        assert final_state.card_id == "C12382-K1"
        assert final_state.customer_id == "C12382"
        assert len(final_state.facts) >= 2
        assert len(final_state.derived) >= 2
        assert len(final_state.inferences) >= 1
        assert len(final_state.investigation_timeline) >= 8

        # HHG-001 Routine Travel verdict
        assert final_state.verdict == "benign"
        assert final_state.fraud_pattern == "routine_travel_anomaly"
        assert final_state.exposure_usd == 0.0
        assert final_state.stop_reason in (StopReason.SUFFICIENT_EVIDENCE, StopReason.CUSTOMER_CONFIRMED)

    def test_hhg014_workflow_execution(self, workflow):
        case_input = {
            "case_id": "HHG-014",
            "trigger_type": "analyst_request",
            "trigger_text": "Analyst request: several cards this month show purchases from the same unusual device profile. Review transaction 3478561 on card C13487-K1.",
            "flagged_txn_id": "3478561",
            "card_id": "C13487-K1",
            "customer_id": "C13487"
        }
        final_state = workflow.run(case_input)

        assert final_state.case_status == CaseStatus.COMPLETED
        assert final_state.verdict == "fraud"
        assert final_state.fraud_pattern == "multi_card_device_cluster"
        assert len(final_state.affected_txn_ids) > 0
        assert final_state.exposure_usd > 0.0
        assert len(final_state.policy_rules_triggered) > 0
        assert len(final_state.recommended_actions) > 0

    def test_stop_conditions_exist_and_terminate(self, workflow):
        case_input = {
            "case_id": "HHG-006",
            "trigger_type": "customer_report",
            "trigger_text": "Customer dispute regarding 3476682",
            "flagged_txn_id": "3476682",
            "card_id": "C07297-K1",
            "customer_id": "C07297"
        }
        final_state = workflow.run(case_input)
        assert final_state.stop_reason is not None
        assert isinstance(final_state.stop_reason, StopReason)
