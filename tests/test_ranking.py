"""BM25 and TF-IDF scores vs hand-computed values on a toy corpus."""

import math

from snu_central.index.inverted_index import InvertedIndex
from snu_central.retrieval.bm25 import BM25Retriever
from snu_central.retrieval.tfidf import TfidfCosineRetriever

# Analyzed terms (no stop words/stemming effects): a=[apple apple banana] b=[banana cherry] c=[cherry date elder fig]
CHUNKS = [
    {"chunk_id": "a", "text": "apple apple banana"},
    {"chunk_id": "b", "text": "banana cherry"},
    {"chunk_id": "c", "text": "cherry date elder fig"},
]
IDX = InvertedIndex.build(CHUNKS)   # N=3, lengths 3,2,4, avg 3


def test_bm25_hand_computed():
    r = BM25Retriever(IDX, CHUNKS, k1=1.5, b=0.75)
    idf = math.log(1 + (3 - 1 + 0.5) / (1 + 0.5))                # df(apple)=1
    norm = 1 - 0.75 + 0.75 * 3 / 3                                # len(a)=avg -> 1
    expected = idf * 2 * 2.5 / (2 + 1.5 * norm)
    assert abs(r.score(["appl"])["a"] - expected) < 1e-9
    assert r.search("apple", 5)[0][0]["chunk_id"] == "a"


def test_bm25_length_normalisation():
    r = BM25Retriever(IDX, CHUNKS)
    s = r.score(["cherri"])          # cherry in b (len 2) and c (len 4): shorter chunk scores higher
    assert s["b"] > s["c"]


def test_tfidf_cosine_hand_computed():
    r = TfidfCosineRetriever(IDX, CHUNKS)
    idf_apple, idf_banana = math.log10(3 / 1), math.log10(3 / 2)
    wa = (1 + math.log10(2)) * idf_apple                          # apple in a, tf=2
    wb = idf_banana                                               # banana in a, tf=1
    norm_a = math.sqrt(wa**2 + wb**2)
    expected = (idf_apple * wa) / (idf_apple * norm_a)            # query = [apple]
    assert abs(r.score(["appl"])["a"] - expected) < 1e-9
    assert all(0 <= v <= 1 + 1e-9 for v in r.score(["appl", "banana", "cherri"]).values())


def test_unknown_terms_score_nothing():
    assert BM25Retriever(IDX, CHUNKS).score(["zzz"]) == {}
    assert TfidfCosineRetriever(IDX, CHUNKS).score(["zzz"]) == {}
