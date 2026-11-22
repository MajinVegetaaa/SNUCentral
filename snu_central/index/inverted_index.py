"""term -> {chunk_id: tf}, df, idf, chunk lengths, avg length (FR-3.1-3.3)."""

import math
from collections import Counter
from dataclasses import dataclass, field

from ..textproc.analyzer import analyze, tokenize


@dataclass
class InvertedIndex:
    postings: dict[str, dict[str, int]] = field(default_factory=dict)   # term -> {chunk_id: tf}
    lengths: dict[str, int] = field(default_factory=dict)               # chunk_id -> number of terms
    n_docs: int = 0
    avg_len: float = 0.0
    idf: dict[str, float] = field(default_factory=dict)                 # TF-IDF idf = log10(N/df)
    surface: dict[str, int] = field(default_factory=dict)               # word as written -> count (spelling, FR-4.11)

    def df(self, term: str) -> int:
        return len(self.postings.get(term, ()))

    @classmethod
    def build(cls, chunks: list[dict]) -> "InvertedIndex":
        idx = cls()
        for c in chunks:
            terms = analyze(c["text"])
            for w in tokenize(c["text"]):
                if w.isalpha():
                    idx.surface[w] = idx.surface.get(w, 0) + 1
            idx.lengths[c["chunk_id"]] = len(terms)
            for term, tf in Counter(terms).items():
                idx.postings.setdefault(term, {})[c["chunk_id"]] = tf
        idx.n_docs = len(chunks)
        idx.avg_len = sum(idx.lengths.values()) / idx.n_docs if idx.n_docs else 0.0
        idx.idf = {t: math.log10(idx.n_docs / len(p)) for t, p in idx.postings.items()}
        return idx
