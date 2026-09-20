"""
RAG Sources Registry, Classification, and Anti-Leakage Boundary.
Guarantees that benchmark answers, evaluation results, and manual investigations
are strictly excluded from the retrieval corpus.
"""

import os
from pathlib import Path
from typing import List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Explicit Anti-Leakage Blacklist: files or directories that MUST NOT be indexed
EXCLUDED_PATTERNS: Set[str] = {
    "manual_case_investigation.md",
    "hhg001_verification.md",
    "hhg014_graph_verification.md",
    "benchmark_coverage_audit.md",
    "real_llm_smoketest.md",
    "case_pack.csv",
    "cases",
    "results",
    "audit_results_cache.json"
}

# Authoritative RAG Sources
AUTHORITATIVE_DOCS = [
    REPO_ROOT / "docs" / "policy_matrix.md",
    REPO_ROOT / "hackathon_spec.txt",
    REPO_ROOT / "docs" / "requirements.md",
]


def is_path_excluded(path_or_filename: str) -> bool:
    """Checks whether a given path or filename matches any excluded pattern."""
    p_str = str(path_or_filename).lower()
    for pattern in EXCLUDED_PATTERNS:
        if pattern.lower() in p_str:
            return True
    return False


def validate_path_allowed(path_or_filename: str) -> None:
    """Raises ValueError if path touches any quarantined benchmark file."""
    if is_path_excluded(path_or_filename):
        raise ValueError(
            f"Security Leakage Violation: Attempted to index or access quarantined benchmark file: {path_or_filename}"
        )


def get_authoritative_sources() -> List[Path]:
    """Returns verified list of authoritative source paths, validating none violate anti-leakage rules."""
    valid_sources = []
    for p in AUTHORITATIVE_DOCS:
        validate_path_allowed(str(p))
        if p.exists():
            valid_sources.append(p)
    return valid_sources
