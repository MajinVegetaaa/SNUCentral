"""CLI search: python -m snu_central.retrieval "attendance" [--ranker bm25|tfidf] [-k 5]"""

import argparse

from ..config import load_config
from . import load_retriever
from .gate import check


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--ranker", choices=["bm25", "tfidf"])
    ap.add_argument("-k", type=int)
    a = ap.parse_args()
    cfg = load_config()
    k = a.k or cfg["retrieval"]["top_k"]
    ret = load_retriever(cfg, a.ranker)
    fix = ret.speller.suggest(a.query)
    if fix:
        print(f"Did you mean: {fix.text}   {fix.changes}")
    res = ret.search(a.query, k)
    gate = check(ret, a.query, res, cfg["retrieval"]["abstain_threshold"])
    print(f"terms: {ret.query_terms(a.query)}   gate: {gate.reason}\n")
    for i, (c, s) in enumerate(res, 1):
        print(f"[{i}] {s:.3f}  {c['document_name']} | p.{c['page_number']} | {c['section']}")
        print(f"    {c['text'][:160]}...\n")


if __name__ == "__main__":
    main()
