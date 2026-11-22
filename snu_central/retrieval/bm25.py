"""BM25 ranking, k1 and b from config (FR-4.4).

score(q, d) = sum over query terms t in d of
    idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d) / avg_len))
    idf(t) = ln(1 + (N - df + 0.5) / (df + 0.5))
"""

import math

from .base import Retriever


class BM25Retriever(Retriever):
    def __init__(self, index, chunks, synonyms_path=None, k1: float = 1.5, b: float = 0.75):
        super().__init__(index, chunks, synonyms_path)
        self.k1, self.b = k1, b

    def idf(self, term: str) -> float:
        df = self.index.df(term)
        return math.log(1 + (self.index.n_docs - df + 0.5) / (df + 0.5))

    def score(self, terms):
        idx, scores = self.index, {}
        for t in terms:
            post = idx.postings.get(t)
            if not post:
                continue
            w = self.idf(t)
            for cid, tf in post.items():
                norm = 1 - self.b + self.b * idx.lengths[cid] / idx.avg_len
                scores[cid] = scores.get(cid, 0.0) + w * tf * (self.k1 + 1) / (tf + self.k1 * norm)
        return scores

    def confidence(self, terms, top_score):
        """top score / best conceivable score (every query term at saturation): ~0..1, independent of query length."""
        ceiling = sum(self.idf(t) * (self.k1 + 1) for t in terms if self.index.df(t))
        return top_score / ceiling if ceiling else 0.0
