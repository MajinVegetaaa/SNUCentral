"""Retriever interface: search(query, k) -> list[(chunk, score)]."""

from abc import ABC, abstractmethod

from ..index.inverted_index import InvertedIndex
from ..textproc.expansion import expand, synonym_words
from ..textproc.spelling import SpellChecker


class Retriever(ABC):
    def __init__(self, index: InvertedIndex, chunks: list[dict], synonyms_path=None):
        self.index = index
        self.chunks = {c["chunk_id"]: c for c in chunks}
        self.synonyms_path = synonyms_path
        self._speller: SpellChecker | None = None

    @property
    def speller(self) -> SpellChecker:
        """Built on first use from the index vocabulary (+ synonym dictionary words), FR-4.11."""
        if self._speller is None:
            extra = synonym_words(self.synonyms_path) if self.synonyms_path else []
            self._speller = SpellChecker(self.index.surface, self.index.postings, extra)
        return self._speller

    def query_terms(self, query: str) -> list[str]:
        """Analyze (+ expand with synonyms when a dictionary is given). Same analyzer as indexing (FR-4.2)."""
        if self.synonyms_path:
            return expand(query, self.synonyms_path)
        from ..textproc.analyzer import analyze
        return list(dict.fromkeys(analyze(query)))

    def confidence(self, terms: list[str], top_score: float) -> float:
        """Top score on a query-independent scale, used by the abstention gate. Default: the score itself."""
        return top_score

    @abstractmethod
    def score(self, terms: list[str]) -> dict[str, float]:
        """chunk_id -> score, for chunks containing at least one query term."""

    def search(self, query: str, k: int = 5) -> list[tuple[dict, float]]:
        scores = self.score(self.query_terms(query))
        top = sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:k]
        return [(self.chunks[cid], s) for cid, s in top]
