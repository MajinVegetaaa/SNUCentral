"""Abstention gate: score threshold + vocabulary check before any LLM call (FR-5.9, FR-5.10)."""

from dataclasses import dataclass


@dataclass
class GateResult:
    answer: bool          # True -> go on to generation
    reason: str           # "ok" | "no_results" | "no_known_terms" | "below_threshold"


def check(retriever, query: str, results: list[tuple[dict, float]], threshold: float | None) -> GateResult:
    terms = retriever.query_terms(query)
    if not any(retriever.index.df(t) for t in terms):
        return GateResult(False, "no_known_terms")      # nothing in the query occurs in any document
    if not results:
        return GateResult(False, "no_results")
    if threshold is not None and retriever.confidence(terms, results[0][1]) < threshold:
        return GateResult(False, "below_threshold")
    return GateResult(True, "ok")
