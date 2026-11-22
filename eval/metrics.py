"""Retrieval metrics (FR-8.2): Precision@K, Recall@K, MRR, and abstention-threshold tuning."""


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return sum(1 for c in ranked[:k] if c in relevant) / k


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return sum(1 for c in ranked[:k] if c in relevant) / len(relevant) if relevant else 0.0


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for i, c in enumerate(ranked, 1):
        if c in relevant:
            return 1 / i
    return 0.0


def tune_threshold(answerable_top: list[float], unanswerable_top: list[float]) -> tuple[float, float]:
    """Pick tau maximising (answerable kept + unanswerable rejected) / total; ties -> LOWEST tau (prefer answering).
    Returns (tau, accuracy). A query is answered iff its top score >= tau."""
    cands = sorted(set(answerable_top + unanswerable_top))
    total = len(answerable_top) + len(unanswerable_top)
    best = (0.0, -1.0)
    for tau in [0.0] + cands:
        ok = sum(s >= tau for s in answerable_top) + sum(s < tau for s in unanswerable_top)
        if ok / total > best[1] + 1e-12:
            best = (tau, ok / total)
    return best
