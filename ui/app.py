"""
TigerGraph Agentic Fraud Investigation — Flask Investigation Console
Built for Hacker House Goa 2026.
Replay Mode: Visualizes authoritative benchmark outputs from Groq + live TigerGraph FraudNet.
"""

import os
import json
import csv
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from flask import Flask, render_template, jsonify, abort, request, redirect, url_for

# Determine project root dynamically from this file location
UI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = UI_DIR.parent
RESULTS_DIR = PROJECT_ROOT / "results" / "groq_tigergraph"
CASE_PACK_CSV = PROJECT_ROOT / "case_pack.csv"

app = Flask(
    __name__,
    template_folder=str(UI_DIR / "templates"),
    static_folder=str(UI_DIR / "static")
)

# -----------------------------------------------------------------------------
# Data Loading & Helper Functions
# -----------------------------------------------------------------------------

def load_cases() -> List[str]:
    """Discovers and numerically sorts all available benchmark result case IDs."""
    if not RESULTS_DIR.exists():
        return []
    
    files = list(RESULTS_DIR.glob("HHG-*.json"))
    
    def case_sort_key(path: Path) -> int:
        match = re.search(r"HHG-(\d+)", path.stem)
        return int(match.group(1)) if match else 999999
        
    sorted_files = sorted(files, key=case_sort_key)
    return [f.stem for f in sorted_files]


def validate_case_id(case_id: str, available_cases: List[str]) -> bool:
    """Strictly validates case_id format and presence to prevent path traversal."""
    if not isinstance(case_id, str):
        return False
    if not re.match(r"^HHG-\d{3}$", case_id):
        return False
    return case_id in available_cases


def load_trigger_context(case_id: str) -> Dict[str, Any]:
    """Loads trigger metadata from case_pack.csv if available."""
    if not CASE_PACK_CSV.exists():
        return {}
    try:
        with open(CASE_PACK_CSV, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("case_id") == case_id:
                    return row
    except Exception:
        pass
    return {}


def load_case(case_id: str) -> Optional[Dict[str, Any]]:
    """Loads a single benchmark result file safely."""
    target_file = (RESULTS_DIR / f"{case_id}.json").resolve()
    
    # Ensure resolved path is strictly within RESULTS_DIR
    try:
        target_file.relative_to(RESULTS_DIR.resolve())
    except ValueError:
        return None
        
    if not target_file.exists():
        return None
        
    try:
        with open(target_file, mode="r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_previous_case(case_id: str, cases: List[str]) -> Optional[str]:
    """Returns the preceding case ID or None if at the first case."""
    if case_id not in cases:
        return None
    idx = cases.index(case_id)
    return cases[idx - 1] if idx > 0 else None


def get_next_case(case_id: str, cases: List[str]) -> Optional[str]:
    """Returns the subsequent case ID or None if at the last case."""
    if case_id not in cases:
        return None
    idx = cases.index(case_id)
    return cases[idx + 1] if idx < len(cases) - 1 else None


def classify_provenance(ref: str, source: str) -> Tuple[str, str]:
    """Categorizes evidence into FACT, ATTESTATION, or INFERENCE with CSS class."""
    ref_str = str(ref or "").lower()
    src_str = str(source or "").lower()
    
    if src_str == "customer" or "customer" in ref_str or "evidence_request" in ref_str:
        return "ATTESTATION (Customer)", "prov-customer"
    elif "get_similar_closed_cases" in ref_str or "similar_closed" in ref_str or "case-cc-" in ref_str:
        return "FACT (Case Memory)", "prov-memory"
    elif src_str == "document" or "policy" in ref_str or "typology" in ref_str:
        return "FACT (Policy / Typology)", "prov-policy"
    elif "llm:" in ref_str or "pattern_reasoner" in ref_str or "reasoner" in ref_str:
        return "INFERENCE (LLM)", "prov-inference"
    elif "get_" in ref_str or src_str == "graph":
        return "FACT (TigerGraph)", "prov-graph"
    else:
        return "FACT (Graph)", "prov-graph"


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------

@app.route("/")
def index():
    """Default route: renders HHG-014 or first available case."""
    cases = load_cases()
    if not cases:
        return render_template("error.html", message="No benchmark results found in results/groq_tigergraph/"), 404
    
    default_case = "HHG-014" if "HHG-014" in cases else cases[0]
    return redirect(url_for("view_case", case_id=default_case))


@app.route("/case/<case_id>")
def view_case(case_id: str):
    """Renders the detailed investigation console for the specified case."""
    cases = load_cases()
    if not cases:
        return render_template("error.html", message="No benchmark results found in results/groq_tigergraph/"), 404
        
    if not validate_case_id(case_id, cases):
        return render_template("error.html", message=f"Invalid or unknown Case ID '{case_id}'. Must be one of {cases[:3]} ..."), 404
        
    data = load_case(case_id)
    if not data:
        return render_template("error.html", message=f"Could not load benchmark data for {case_id}."), 500
        
    prev_case = get_previous_case(case_id, cases)
    next_case = get_next_case(case_id, cases)
    trigger = load_trigger_context(case_id)
    
    case_obj = data.get("case", {})
    evidence_raw = case_obj.get("evidence", [])
    
    # Enrich evidence items with categorized provenance
    evidence_items = []
    for ev in evidence_raw:
        tag_label, tag_class = classify_provenance(ev.get("ref", ""), ev.get("source", "graph"))
        evidence_items.append({
            "claim": ev.get("claim", ""),
            "ref": ev.get("ref", ""),
            "source": ev.get("source", "graph"),
            "entity_ids": ev.get("entity_ids", []),
            "tag_label": tag_label,
            "tag_class": tag_class
        })
        
    # Format raw JSON safely for the technical trace
    formatted_json = json.dumps(data, indent=2)
    
    return render_template(
        "index.html",
        case_id=case_id,
        cases=cases,
        prev_case=prev_case,
        next_case=next_case,
        data=data,
        case=case_obj,
        trigger=trigger,
        evidence_items=evidence_items,
        sar=data.get("sar", {}),
        next_best_actions=data.get("next_best_actions", {}),
        evidence_requests=data.get("evidence_requests", []),
        raw_json=formatted_json
    )


@app.route("/api/cases")
def api_cases():
    """API endpoint returning available case IDs."""
    cases = load_cases()
    return jsonify({"cases": cases, "count": len(cases)})


@app.route("/api/case/<case_id>")
def api_case(case_id: str):
    """API endpoint returning JSON for a specific case."""
    cases = load_cases()
    if not validate_case_id(case_id, cases):
        abort(404, description=f"Case {case_id} not found.")
    data = load_case(case_id)
    if not data:
        abort(500, description=f"Failed to read data for {case_id}.")
    return jsonify(data)


@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", message=str(e.description if hasattr(e, 'description') else "Page not found")), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("error.html", message="An unexpected error occurred while loading case data."), 500


# -----------------------------------------------------------------------------
# CLI Entrypoint
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
