"""
Unit and Integration Tests for Phase 3C: Real LLM Investigation Agent.
Tests:
- Provider abstraction, structured output parsing, JSON repair, credential scrubbing
- Grounding validator and hallucinated entity rejection
- Step guard (preventing runaway loops)
- Policy boundary enforcement and timeline override audit events
- Evidence-request loop, simulated responses, initial vs final assessment preservation
- End-to-end benchmark execution for HHG-001 and HHG-014
- Schema validation and Entity ID integrity
"""

import pytest
from typing import Dict, Any

from src.agent.state import InvestigationState, CaseStatus, StopReason
from src.agent.tools.contracts import InvestigationTools
from pydantic import ValidationError
from src.agent.llm.base import BaseLLMProvider, LLMResponse, TokenUsage, redact_credentials
from src.agent.llm.schemas import (
    LLMReasoningStep,
    LLMFinalSynthesis,
    StructuredFinding,
    ToolCallProposal,
    EvidenceRequestProposal
)
from src.agent.llm.mock import MockLLMProvider
from src.agent.llm.factory import get_llm_provider
from src.agent.grounding import get_grounding_validator, GroundingValidator
from src.agent.workflow import InvestigationWorkflow
from src.agent.serializer import serialize_case_answer
from src.graph.adapter import GraphAdapter
from evaluation.validate_schema import validate_case_answer
from evaluation.check_integrity import check_case_integrity


@pytest.fixture
def mock_tools():
    adapter = GraphAdapter(backend="in_memory")
    return InvestigationTools(adapter=adapter)


@pytest.fixture
def mock_llm():
    return MockLLMProvider()


@pytest.fixture
def validator():
    return get_grounding_validator()


class TestLLMProviderAbstraction:
    """Tests for BaseLLMProvider, MockLLMProvider, TokenUsage, and Credential Scrubbing."""

    def test_mock_llm_generation(self, mock_llm):
        resp = mock_llm.generate([{"role": "user", "content": "Analyze case HHG-001"}])
        assert isinstance(resp, LLMResponse)
        assert resp.content != ""
        assert resp.token_usage.total_tokens > 0

    def test_mock_llm_structured_reasoning_step(self, mock_llm):
        step = mock_llm.generate_structured(
            messages=[{"role": "user", "content": "Inspect HHG-001 3514030 with card_history"}],
            response_model=LLMReasoningStep
        )
        assert isinstance(step, LLMReasoningStep)
        assert step.thought != ""
        assert step.uncertainty in ("low", "medium", "high")
        assert len(step.observations) > 0

    def test_credential_scrubbing(self):
        sensitive_text = "Connecting with Bearer sk-ant-api03-abcdef1234567890 and password=SuperSecretPassword123!"
        scrubbed = redact_credentials(sensitive_text)
        assert "sk-ant" not in scrubbed
        assert "SuperSecretPassword123!" not in scrubbed
        assert "[REDACTED" in scrubbed

    def test_json_repair_and_parse(self, mock_llm):
        # Markdown fenced json with trailing comma
        messy_json = "```json\n{\"thought\": \"analysis\", \"observations\": [\"obs1\",],}\n```"
        parsed = mock_llm.repair_and_parse_json(messy_json)
        assert parsed["thought"] == "analysis"
        assert parsed["observations"] == ["obs1"]

    def test_provider_factory(self):
        p1 = get_llm_provider("mock")
        assert isinstance(p1, MockLLMProvider)

    def test_structured_finding_source_policy_normalization(self):
        """Model-facing source='policy' or 'policy_matrix' must normalize to 'document'."""
        # 1. source='policy' -> 'document'
        f1 = StructuredFinding(claim="Rule R1 triggered", source="policy", ref="POLICY-R1")
        assert f1.source == "document"

        # 2. source='policy_matrix' -> 'document'
        f2 = StructuredFinding(claim="Rule R3 charge confirmed", source="policy_matrix", ref="POLICY-R3")
        assert f2.source == "document"

        # 3. Canonical sources remain valid
        assert StructuredFinding(claim="Live txn", source="graph", ref="3514030").source == "graph"
        assert StructuredFinding(claim="Case doc", source="document", ref="POLICY-R6").source == "document"
        assert StructuredFinding(claim="Cardholder call", source="customer", ref="inquiry").source == "customer"
        assert StructuredFinding(claim="External feed", source="external", ref="lexis").source == "external"

        # 4. Unknown sources still raise ValidationError
        with pytest.raises(ValidationError):
            StructuredFinding(claim="Bad claim", source="hallucinated_source_abc", ref="ref")

    def test_llm_reasoning_step_with_policy_source_succeeds_without_repair(self):
        """When LLM returns findings with source='policy', LLMReasoningStep validates on first attempt."""
        raw_llm_data = {
            "thought": "Synthesizing evidence with policy rules.",
            "observations": ["Observed cross-region activity"],
            "hypotheses": ["Card testing"],
            "findings": [
                {"claim": "Txn amount is $77.07", "source": "graph", "ref": "3514030", "entity_ids": ["3514030"]},
                {"claim": "Policy R1 applies to weak signals", "source": "policy", "ref": "POLICY-R1", "entity_ids": []}
            ],
            "uncertainty": "low"
        }
        step = LLMReasoningStep(**raw_llm_data)
        assert len(step.findings) == 2
        assert step.findings[0].source == "graph"
        assert step.findings[1].source == "document"

    def test_assess_evidence_prompt_instructs_allowed_sources_and_document_policy(self):
        """Model-facing prompt in assess_evidence must explicitly instruct allowed source values."""
        import inspect
        from src.agent.nodes import InvestigationNodes
        source_code = inspect.getsource(InvestigationNodes.assess_evidence)
        assert "'graph', 'document', 'customer', or 'external'" in source_code
        assert "must be classified under source: 'document'" in source_code


class TestGroundingAndIntegrity:
    """Tests for entity verification, hallucination rejection, and exposure calculations."""

    def test_valid_vs_hallucinated_txn_filtering(self, validator):
        candidate_ids = ["3514030", "9999999_FABRICATED", "3478561"]
        valid, rejected = validator.filter_valid_txn_ids(candidate_ids)
        assert "3514030" in valid
        assert "3478561" in valid
        assert "9999999_FABRICATED" in rejected

    def test_hallucinated_card_filtering(self, validator):
        candidate_cards = ["C12382-K1", "FAKE-CARD-999"]
        valid, rejected = validator.filter_valid_card_ids(candidate_cards)
        assert "C12382-K1" in valid
        assert "FAKE-CARD-999" in rejected

    def test_grounded_exposure_calculation(self, validator):
        # 3514030 is $77.07 in dataset
        exp = validator.compute_grounded_exposure(["3514030"])
        assert exp == 77.07

    def test_evidence_item_sanitization(self, validator):
        dirty_evidence = [{
            "claim": "Suspicious charge identified.",
            "source": "graph",
            "ref": "test",
            "entity_ids": ["3514030", "HALLUCINATED_TXN_000"]
        }]
        cleaned = validator.sanitize_evidence_items(dirty_evidence)
        assert len(cleaned) == 1
        assert "3514030" in cleaned[0]["entity_ids"]
        assert "HALLUCINATED_TXN_000" not in cleaned[0]["entity_ids"]


class TestPolicyBoundariesAndWorkflowGuards:
    """Tests for Policy Engine supremacy, override auditing, step guard, and evidence loops."""

    def test_policy_override_auditing(self, mock_tools):
        """When LLM recommends an unapproved action, PolicyEngine overrules it and logs to timeline."""
        workflow = InvestigationWorkflow(tools=mock_tools)
        state = InvestigationState(
            case_id="HHG-001",
            trigger_type="risk_score",
            flagged_txn_id="3514030",
            card_id="C12382-K1",
            customer_id="C12382"
        )
        # Simulate LLM erroneously suggesting BLOCK_CARD on legitimate card
        state.llm_proposed_actions = ["BLOCK_CARD", "FILE_REPORT"]
        state.verdict = "benign"
        state.customer_response = "confirmed"

        from src.agent.nodes import InvestigationNodes
        state = InvestigationNodes.apply_policy(state, mock_tools)

        # PolicyEngine must enforce statutory actions
        assert "CLOSE_NO_FRAUD" in state.recommended_actions
        assert "BLOCK_CARD" not in state.recommended_actions

        # Override must be logged to timeline
        override_events = [e for e in state.investigation_timeline if e.stage == "policy_override"]
        assert len(override_events) == 1
        assert "Deterministic PolicyEngine overrode LLM suggestions" in override_events[0].evidence_discovered

    def test_step_guard_enforcement(self, mock_tools):
        """Step guard limits execution turns to prevent infinite loops."""
        limited_workflow = InvestigationWorkflow(tools=mock_tools, max_steps=4)
        case_input = {
            "case_id": "HHG-001",
            "trigger_type": "risk_score",
            "trigger_text": "Scored at 0.61",
            "flagged_txn_id": "3514030",
            "card_id": "C12382-K1",
            "customer_id": "C12382"
        }
        state = limited_workflow.run(case_input)
        assert state.case_status == CaseStatus.COMPLETED
        step_events = [e for e in state.investigation_timeline if e.stage == "step_guard"]
        assert len(step_events) >= 1

    def test_evidence_request_loop_preserves_assessments(self, mock_tools, mock_llm):
        """Evidence request loop records simulated response and preserves initial vs final assessment."""
        workflow = InvestigationWorkflow(tools=mock_tools, llm_provider=mock_llm)
        case_input = {
            "case_id": "HHG-001",
            "trigger_type": "risk_score",
            "trigger_text": "Real-time model scored transaction 3514030 ($77.07, in billing region 444.0) at 0.61.",
            "flagged_txn_id": "3514030",
            "card_id": "C12382-K1",
            "customer_id": "C12382"
        }
        state = workflow.run(case_input)

        assert state.initial_assessment is not None
        assert state.final_assessment is not None
        assert len(state.evidence_requests) >= 1
        assert len(state.evidence_responses) >= 1
        assert state.customer_response == "confirmed"
        assert state.final_assessment["verdict"] == "benign"


class TestBenchmarkEndToEndReasoning:
    """Full end-to-end validation of HHG-001 and HHG-014 through workflow, serializer, and validators."""

    def test_hhg001_full_lifecycle(self, mock_tools, mock_llm):
        workflow = InvestigationWorkflow(tools=mock_tools, llm_provider=mock_llm)
        case_input = {
            "case_id": "HHG-001",
            "trigger_type": "risk_score",
            "trigger_text": "Real-time model scored transaction 3514030 ($77.07, in billing region 444.0) at 0.61.",
            "flagged_txn_id": "3514030",
            "card_id": "C12382-K1",
            "customer_id": "C12382"
        }
        state = workflow.run(case_input)
        answer = serialize_case_answer(state)

        # 1. Schema Validation
        val_res = validate_case_answer(answer)
        assert val_res.is_valid is True, f"Schema errors: {val_res.errors}"

        # 2. Entity Integrity Check
        integrity_errs = check_case_integrity(answer)
        assert len(integrity_errs) == 0, f"Integrity errors: {integrity_errs}"

        # 3. Domain Logic Invariants
        assert answer["case"]["verdict"] == "legitimate"
        assert answer["case"]["pattern"] == "none"
        assert answer["case"]["exposure_usd"] == 0.0
        assert answer["sar"]["file"] is False
        assert answer["next_best_actions"]["final"][0]["action"] == "CLOSE_NO_FRAUD"

    def test_hhg014_full_lifecycle(self, mock_tools, mock_llm):
        workflow = InvestigationWorkflow(tools=mock_tools, llm_provider=mock_llm)
        case_input = {
            "case_id": "HHG-014",
            "trigger_type": "analyst_request",
            "trigger_text": "Analyst request: several cards this month show purchases from the same unusual device profile. Review transaction 3478561 on card C13487-K1.",
            "flagged_txn_id": "3478561",
            "card_id": "C13487-K1",
            "customer_id": "C13487"
        }
        state = workflow.run(case_input)
        answer = serialize_case_answer(state)

        # 1. Schema Validation
        val_res = validate_case_answer(answer)
        assert val_res.is_valid is True, f"Schema errors: {val_res.errors}"

        # 2. Entity Integrity Check
        integrity_errs = check_case_integrity(answer)
        assert len(integrity_errs) == 0, f"Integrity errors: {integrity_errs}"

        # 3. Domain Logic Invariants
        assert answer["case"]["verdict"] == "fraud"
        assert answer["case"]["pattern"] == "undocumented"
        assert answer["case"]["pattern_description"] != ""
        assert answer["case"]["exposure_usd"] == 74.96
        assert answer["sar"]["file"] is True
        assert len(answer["sar"]["narrative"].split(".")) >= 3
        final_actions = [a["action"] for a in answer["next_best_actions"]["final"]]
        assert "FILE_REPORT" in final_actions
        assert "CREATE_CASE" in final_actions
