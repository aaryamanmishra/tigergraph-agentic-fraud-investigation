"""
In-Memory Policy and Typology Retriever for GraphRAG.
Provides fast, deterministic BM25 / token-frequency retrieval across authoritative policies,
canonical action definitions, and fraud typologies with full provenance tracking.
Zero external API calls, zero heavy embeddings, 100% reproducible.
"""

import math
import re
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

from src.rag.sources import get_authoritative_sources, validate_path_allowed, REPO_ROOT
from src.rag.chunker import PolicyChunker, DocumentChunk
from src.rag.provenance import ProvenanceItem, ProvenanceType


class InvertedIndex:
    """Lightweight in-memory BM25-like search index."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks: List[DocumentChunk] = []
        self.doc_len: List[int] = []
        self.avg_dl: float = 0.0
        self.term_df: Dict[str, int] = {}
        self.doc_term_freq: List[Dict[str, int]] = []

    def _tokenize(self, text: str) -> List[str]:
        cleaned = re.sub(r"[^a-zA-Z0-9_\$]", " ", text.lower())
        tokens = [t for t in cleaned.split() if len(t) > 1]
        return tokens

    def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        start_idx = len(self.chunks)
        self.chunks.extend(chunks)

        for i, chunk in enumerate(chunks, start=start_idx):
            # Combine content, title, and keywords (keywords have high relevance)
            text = f"{chunk.title} {chunk.title} {' '.join(chunk.keywords)} {' '.join(chunk.keywords)} {chunk.content}"
            tokens = self._tokenize(text)
            self.doc_len.append(len(tokens))

            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self.doc_term_freq.append(tf)

            for t in set(tokens):
                self.term_df[t] = self.term_df.get(t, 0) + 1

        total_docs = len(self.chunks)
        if total_docs > 0:
            self.avg_dl = sum(self.doc_len) / total_docs

    def search(
        self,
        query: str,
        top_k: int = 3,
        source_type: Optional[ProvenanceType] = None
    ) -> List[tuple[DocumentChunk, float]]:
        query_tokens = self._tokenize(query)
        if not query_tokens or not self.chunks:
            return []

        scores: List[tuple[int, float]] = []
        total_docs = len(self.chunks)

        for i, chunk in enumerate(self.chunks):
            if source_type and chunk.source_type != source_type:
                continue

            score = 0.0
            doc_tf = self.doc_term_freq[i]
            dl = self.doc_len[i]

            for qt in query_tokens:
                if qt in doc_tf:
                    freq = doc_tf[qt]
                    df = self.term_df.get(qt, 1)
                    idf = math.log(1.0 + (total_docs - df + 0.5) / (df + 0.5))
                    num = freq * (self.k1 + 1.0)
                    denom = freq + self.k1 * (1.0 - self.b + self.b * (dl / (self.avg_dl or 1.0)))
                    score += idf * (num / denom)

            # Keyword direct match boost
            for kw in chunk.keywords:
                if kw.lower() in query.lower():
                    score += 2.5

            if score > 0.0:
                scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        results = [(self.chunks[idx], s) for idx, s in scores[:top_k]]
        return results


class PolicyRetriever:
    """Singleton/service managing in-memory retrieval of policies and typologies."""

    def __init__(self):
        self.index = InvertedIndex()
        self._initialize_index()

    def _initialize_index(self) -> None:
        """Loads and chunks authoritative docs into the search index."""
        policy_path = REPO_ROOT / "docs" / "policy_matrix.md"
        spec_path = REPO_ROOT / "hackathon_spec.txt"

        all_chunks: List[DocumentChunk] = []

        if policy_path.exists():
            validate_path_allowed(str(policy_path))
            all_chunks.extend(PolicyChunker.chunk_policy_matrix(policy_path))

        if spec_path.exists():
            validate_path_allowed(str(spec_path))
            all_chunks.extend(PolicyChunker.chunk_spec_and_typologies(spec_path))

        self.index.add_chunks(all_chunks)

    def retrieve_policies(self, query: str, top_k: int = 3) -> List[ProvenanceItem]:
        """Retrieves top matching policy rules or action definitions."""
        matches = self.index.search(query, top_k=top_k, source_type=ProvenanceType.POLICY)
        return [chunk.to_provenance_item(score=score) for chunk, score in matches]

    def retrieve_typologies(self, query: str, top_k: int = 2) -> List[ProvenanceItem]:
        """Retrieves top matching fraud typologies."""
        matches = self.index.search(query, top_k=top_k, source_type=ProvenanceType.TYPOLOGY)
        return [chunk.to_provenance_item(score=score) for chunk, score in matches]

    def retrieve(self, query: str, top_k: int = 5) -> List[ProvenanceItem]:
        """Retrieves top matching chunks across all authoritative categories."""
        matches = self.index.search(query, top_k=top_k)
        return [chunk.to_provenance_item(score=score) for chunk, score in matches]


# Global singleton instance
_GLOBAL_RETRIEVER: Optional[PolicyRetriever] = None


def get_policy_retriever() -> PolicyRetriever:
    global _GLOBAL_RETRIEVER
    if _GLOBAL_RETRIEVER is None:
        _GLOBAL_RETRIEVER = PolicyRetriever()
    return _GLOBAL_RETRIEVER
