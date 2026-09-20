"""
Answer File JSON Schema and Cross-Field Invariant Validator.
Enforces docs/answer_schema.md specification.
"""

import re
import json
from typing import Dict, List, Any, Tuple, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from src.policy.actions import Action, ApprovalRoute, get_statutory_approval_route, validate_action_route


VALID_PATTERNS = {
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "none"
}

VALID_STATUSES = {"open", "closed_fraud", "closed_legitimate", "escalated"}
VALID_VERDICTS = {"fraud", "legitimate", "uncertain"}
VALID_EVIDENCE_SOURCES = {"graph", "document", "customer", "external"}
VALID_REQUEST_TYPES = {"customer_validation", "step_up_auth", "analyst_info"}


class ValidationResult:
    def __init__(self, is_valid: bool, errors: List[str], warnings: List[str]):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings

    def __repr__(self):
        status = "PASSED" if self.is_valid else "FAILED"
        return f"<ValidationResult status={status} errors={len(self.errors)} warnings={len(self.warnings)}>"


def validate_action_item(item: Any, path: str) -> List[str]:
    errors = []
    if not isinstance(item, dict):
        return [f"{path}: action item must be an object"]
    
    for req in ["action", "route", "reason"]:
        if req not in item:
            errors.append(f"{path}: missing required field '{req}'")

    action_val = item.get("action")
    route_val = item.get("route")

    valid_actions = {a.value for a in Action}
    valid_routes = {r.value for r in ApprovalRoute}

    if action_val not in valid_actions:
        errors.append(f"{path}: invalid action '{action_val}'. Must be one of {sorted(list(valid_actions))}")

    if route_val not in valid_routes:
        errors.append(f"{path}: invalid route '{route_val}'. Must be one of {sorted(list(valid_routes))}")

    if action_val in valid_actions and route_val in valid_routes:
        act = Action(action_val)
        rt = ApprovalRoute(route_val)
        # Check routing compatibility
        # For BLOCK_CARD, route depends on exposure; otherwise check statutory
        if act == Action.DECLINE_TRANSACTION and rt != ApprovalRoute.L1:
            errors.append(f"{path}: DECLINE_TRANSACTION requires route 'L1', got '{route_val}'")
        elif act == Action.FILE_REPORT and rt != ApprovalRoute.L2:
            errors.append(f"{path}: FILE_REPORT requires route 'L2', got '{route_val}'")
        elif act == Action.BLOCK_ALL_CARDS and rt != ApprovalRoute.L2:
            errors.append(f"{path}: BLOCK_ALL_CARDS requires route 'L2', got '{route_val}'")
        elif act not in (Action.DECLINE_TRANSACTION, Action.BLOCK_CARD, Action.BLOCK_ALL_CARDS, Action.FILE_REPORT):
            if rt != ApprovalRoute.AUTO:
                errors.append(f"{path}: action '{action_val}' must have route 'auto', got '{route_val}'")

    return errors


def validate_case_answer(data: Dict[str, Any]) -> ValidationResult:
    """
    Validates a complete case answer dictionary against schema and cross-field invariants.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Top Level Fields
    required_top = [
        "case_id", "case", "evidence_requests", "next_best_actions",
        "sar", "stop_reason", "tool_calls", "tokens", "latency_s"
    ]
    for field in required_top:
        if field not in data:
            errors.append(f"Top-level missing required field: '{field}'")

    case_id = data.get("case_id", "")
    if not isinstance(case_id, str) or not re.match(r"^HHG-[0-9]{3}$", case_id):
        errors.append(f"case_id must be in format 'HHG-xxx', got '{case_id}'")

    if not isinstance(data.get("stop_reason"), str) or not data.get("stop_reason", "").strip():
        errors.append("stop_reason must be a non-empty string")

    for num_field in ["tool_calls", "tokens"]:
        val = data.get(num_field)
        if not isinstance(val, int) or val < 0:
            errors.append(f"{num_field} must be a non-negative integer, got {val}")

    lat = data.get("latency_s")
    if not isinstance(lat, (int, float)) or lat < 0.0:
        errors.append(f"latency_s must be a non-negative number, got {lat}")

    # Evidence requests
    ev_reqs = data.get("evidence_requests")
    if not isinstance(ev_reqs, list):
        errors.append("evidence_requests must be a list")
    else:
        for i, req in enumerate(ev_reqs):
            if not isinstance(req, dict):
                errors.append(f"evidence_requests[{i}] must be an object")
                continue
            for rf in ["type", "asked_after_step", "assumed_response"]:
                if rf not in req:
                    errors.append(f"evidence_requests[{i}] missing '{rf}'")
            if req.get("type") not in VALID_REQUEST_TYPES:
                errors.append(f"evidence_requests[{i}].type invalid: '{req.get('type')}'")
            if not isinstance(req.get("asked_after_step"), int) or req.get("asked_after_step", 0) < 1:
                errors.append(f"evidence_requests[{i}].asked_after_step must be >= 1")
            if not isinstance(req.get("assumed_response"), str) or not req.get("assumed_response"):
                errors.append(f"evidence_requests[{i}].assumed_response must be a non-empty string")

    # 2. Part 1: Case Object
    case_obj = data.get("case")
    exposure_usd = 0.0
    if not isinstance(case_obj, dict):
        errors.append("'case' must be an object")
    else:
        required_case = [
            "status", "verdict", "fraud_probability", "pattern", "pattern_description",
            "affected_txn_ids", "first_suspicious_txn_id", "connected_card_ids",
            "connected_device_profiles", "exposure_usd", "evidence", "similar_prior_cases",
            "summary", "written_to_graph", "graph_case_id"
        ]
        for cf in required_case:
            if cf not in case_obj:
                errors.append(f"case missing required field: '{cf}'")

        status = case_obj.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"case.status invalid: '{status}'. Must be one of {sorted(list(VALID_STATUSES))}")

        verdict = case_obj.get("verdict")
        if verdict not in VALID_VERDICTS:
            errors.append(f"case.verdict invalid: '{verdict}'. Must be one of {sorted(list(VALID_VERDICTS))}")

        prob = case_obj.get("fraud_probability")
        if not isinstance(prob, (int, float)) or prob < 0.0 or prob > 1.0:
            errors.append(f"case.fraud_probability must be between 0.0 and 1.0, got {prob}")

        pattern = case_obj.get("pattern")
        if pattern not in VALID_PATTERNS:
            errors.append(f"case.pattern invalid: '{pattern}'. Must be one of {sorted(list(VALID_PATTERNS))}")

        pat_desc = case_obj.get("pattern_description", "")
        if pattern == "undocumented" and (not isinstance(pat_desc, str) or not pat_desc.strip()):
            errors.append("case.pattern_description must be non-empty when pattern is 'undocumented'")
        elif pattern != "undocumented" and pat_desc != "":
            errors.append(f"case.pattern_description must be empty string when pattern is not 'undocumented', got '{pat_desc}'")

        affected_txns = case_obj.get("affected_txn_ids")
        if not isinstance(affected_txns, list):
            errors.append("case.affected_txn_ids must be a list of strings")
        else:
            for tid in affected_txns:
                if not isinstance(tid, str):
                    errors.append(f"case.affected_txn_ids item '{tid}' is not a string")

        exp = case_obj.get("exposure_usd")
        if not isinstance(exp, (int, float)) or exp < 0.0:
            errors.append(f"case.exposure_usd must be a non-negative number, got {exp}")
        else:
            exposure_usd = float(exp)

        # Invariant: Legitimate verdict consistency
        if verdict == "legitimate":
            if affected_txns != []:
                errors.append(f"case.affected_txn_ids must be empty for legitimate verdict, got {affected_txns}")
            if exposure_usd != 0.0:
                errors.append(f"case.exposure_usd must be 0.0 for legitimate verdict, got {exposure_usd}")
            if pattern != "none":
                errors.append(f"case.pattern must be 'none' for legitimate verdict, got '{pattern}'")

        # Invariant: Fraud verdict consistency
        if verdict == "fraud":
            if not affected_txns:
                errors.append("case.affected_txn_ids must not be empty for fraud verdict")
            if exposure_usd <= 0.0:
                errors.append("case.exposure_usd must be > 0 for fraud verdict")

        # Evidence array validation
        evidence_list = case_obj.get("evidence")
        if not isinstance(evidence_list, list):
            errors.append("case.evidence must be a list")
        else:
            for i, ev in enumerate(evidence_list):
                if not isinstance(ev, dict):
                    errors.append(f"case.evidence[{i}] must be an object")
                    continue
                for ef in ["claim", "source", "ref", "entity_ids"]:
                    if ef not in ev:
                        errors.append(f"case.evidence[{i}] missing '{ef}'")
                if ev.get("source") not in VALID_EVIDENCE_SOURCES:
                    errors.append(f"case.evidence[{i}].source invalid: '{ev.get('source')}'")
                if not isinstance(ev.get("claim"), str) or not ev.get("claim"):
                    errors.append(f"case.evidence[{i}].claim must be a non-empty string")
                if not isinstance(ev.get("ref"), str) or not ev.get("ref"):
                    errors.append(f"case.evidence[{i}].ref must be a non-empty string")
                if not isinstance(ev.get("entity_ids"), list):
                    errors.append(f"case.evidence[{i}].entity_ids must be a list of strings")

        # Graph persistence consistency
        written = case_obj.get("written_to_graph")
        graph_case_id = case_obj.get("graph_case_id")
        if not isinstance(written, bool):
            errors.append("case.written_to_graph must be boolean")
        if not isinstance(graph_case_id, str):
            errors.append("case.graph_case_id must be a string")
        if written is True and (not graph_case_id or not graph_case_id.strip()):
            errors.append("case.graph_case_id cannot be empty when written_to_graph is true")
        if written is False and graph_case_id != "":
            errors.append("case.graph_case_id must be empty string when written_to_graph is false")

    # 3. Part 2: SAR Object
    sar_obj = data.get("sar")
    sar_file = False
    if not isinstance(sar_obj, dict):
        errors.append("'sar' must be an object")
    else:
        required_sar = ["file", "reason", "narrative", "subjects", "total_amount_usd", "activity_dates"]
        for sf in required_sar:
            if sf not in sar_obj:
                errors.append(f"sar missing required field: '{sf}'")

        sar_file = sar_obj.get("file")
        if not isinstance(sar_file, bool):
            errors.append("sar.file must be boolean")
        else:
            if sar_file is True:
                narrative = sar_obj.get("narrative", "")
                if not isinstance(narrative, str) or len(narrative.strip().split(".")) < 3:
                    errors.append("sar.narrative must be a substantial narrative (at least 3-6 sentences) when file is true")
                subjects = sar_obj.get("subjects")
                if not isinstance(subjects, list) or len(subjects) == 0:
                    errors.append("sar.subjects must be a non-empty list of subject strings when file is true")
                tot_amt = sar_obj.get("total_amount_usd")
                if not isinstance(tot_amt, (int, float)) or tot_amt <= 0:
                    errors.append(f"sar.total_amount_usd must be > 0 when file is true, got {tot_amt}")
                if abs(tot_amt - exposure_usd) > 0.01:
                    errors.append(f"sar.total_amount_usd ({tot_amt}) must match case.exposure_usd ({exposure_usd})")
                dates = sar_obj.get("activity_dates")
                if not isinstance(dates, list) or len(dates) != 2:
                    errors.append(f"sar.activity_dates must contain exactly 2 date strings [start, end], got {dates}")
                else:
                    for d in dates:
                        if not isinstance(d, str) or not re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", d):
                            errors.append(f"sar.activity_dates invalid date format '{d}', expected YYYY-MM-DD")
            else:
                if sar_obj.get("narrative") != "":
                    errors.append("sar.narrative must be empty string when file is false")
                if sar_obj.get("subjects") != []:
                    errors.append(f"sar.subjects must be empty list when file is false, got {sar_obj.get('subjects')}")
                if sar_obj.get("total_amount_usd") != 0.0 and sar_obj.get("total_amount_usd") != 0:
                    errors.append(f"sar.total_amount_usd must be 0 when file is false, got {sar_obj.get('total_amount_usd')}")
                if sar_obj.get("activity_dates") != []:
                    errors.append(f"sar.activity_dates must be empty list when file is false, got {sar_obj.get('activity_dates')}")

    # 4. Part 3: Next Best Actions Object
    nba_obj = data.get("next_best_actions")
    if not isinstance(nba_obj, dict):
        errors.append("'next_best_actions' must be an object")
    else:
        for k in ["initial", "final", "what_changed"]:
            if k not in nba_obj:
                errors.append(f"next_best_actions missing required field: '{k}'")

        initial_acts = nba_obj.get("initial")
        final_acts = nba_obj.get("final")
        what_changed = nba_obj.get("what_changed")

        if not isinstance(initial_acts, list) or len(initial_acts) == 0:
            errors.append("next_best_actions.initial must be a non-empty list")
        else:
            for i, act in enumerate(initial_acts):
                errors.extend(validate_action_item(act, f"next_best_actions.initial[{i}]"))

        if not isinstance(final_acts, list) or len(final_acts) == 0:
            errors.append("next_best_actions.final must be a non-empty list")
        else:
            has_file_report = False
            for i, act in enumerate(final_acts):
                errors.extend(validate_action_item(act, f"next_best_actions.final[{i}]"))
                if act.get("action") == "FILE_REPORT":
                    has_file_report = True

                # Check BLOCK_CARD routing against exposure_usd
                if act.get("action") == "BLOCK_CARD":
                    expected_route = "L2" if exposure_usd > 2500.0 else "L1"
                    if act.get("route") != expected_route:
                        errors.append(
                            f"next_best_actions.final[{i}]: BLOCK_CARD route must be '{expected_route}' "
                            f"for exposure ${exposure_usd:,.2f}, got '{act.get('route')}'"
                        )

            # Invariant: SAR file must agree with FILE_REPORT presence
            if sar_file is True and not has_file_report:
                errors.append("sar.file is true but 'FILE_REPORT' is missing from next_best_actions.final")
            elif sar_file is False and has_file_report:
                errors.append("sar.file is false but 'FILE_REPORT' is present in next_best_actions.final")

        if not isinstance(what_changed, str) or not what_changed.strip():
            errors.append("next_best_actions.what_changed must be a non-empty string")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_answer_file(file_path: str) -> ValidationResult:
    """Reads a JSON file from disk and validates it."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return ValidationResult(is_valid=False, errors=[f"JSON parse error: {str(e)}"], warnings=[])

    return validate_case_answer(data)
