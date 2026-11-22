"""TF-IDF vectors + cosine similarity baseline (FR-4.3, FR-3.3).

weight(t, d) = (1 + log10 tf) * log10(N / df)       (lecture formula; idf from the index)
score(q, d)  = cos(q, d) = (q . d) / (|q| |d|)      query weights: tf = 1 per distinct term
"""

import math

from .base import Retriever


class TfidfCosineRetriever(Retriever):
    def __init__(self, index, chunks, synonyms_path=None):
        super().__init__(index, chunks, synonyms_path)
        sq: dict[str, float] = {}
        for t, post in index.postings.items():
            for cid, tf in post.items():
                sq[cid] = sq.get(cid, 0.0) + (self.weight(t, tf)) ** 2
        self.doc_norm = {cid: math.sqrt(v) for cid, v in sq.items()}

    def weight(self, term: str, tf: int) -> float:
        return (1 + math.log10(tf)) * self.index.idf[term]

    def score(self, terms):
        idx, dots = self.index, {}
        q_norm_sq = 0.0
        for t in terms:
            post = idx.postings.get(t)
            if not post:
                continue
            wq = idx.idf[t]
            q_norm_sq += wq * wq
            for cid, tf in post.items():
                dots[cid] = dots.get(cid, 0.0) + wq * self.weight(t, tf)
        if not dots or q_norm_sq == 0:
            return {}
        qn = math.sqrt(q_norm_sq)
        return {cid: d / (qn * self.doc_norm[cid]) for cid, d in dots.items() if self.doc_norm[cid] > 0}
