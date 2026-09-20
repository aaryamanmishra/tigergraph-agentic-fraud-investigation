"""
Structured Provenance Tracking for GraphRAG Evidence.
Ensures every chunk, policy rule, and historical case cited carries traceable provenance.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


class ProvenanceType(str, Enum):
    GRAPH = "GRAPH"
    CASE_MEMORY = "CASE_MEMORY"
    POLICY = "POLICY"
    TYPOLOGY = "TYPOLOGY"
    SPEC = "SPEC"


@dataclass
class ProvenanceItem:
    """Strongly-typed item representing a traceable piece of evidence or policy guidance."""
    provenance_id: str
    source_type: ProvenanceType
    title: str
    ref: str
    content: str
    score: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provenance_id": self.provenance_id,
            "source_type": self.source_type.value if isinstance(self.source_type, ProvenanceType) else self.source_type,
            "title": self.title,
            "ref": self.ref,
            "content": self.content,
            "score": round(self.score, 4),
            "metadata": self.metadata
        }
