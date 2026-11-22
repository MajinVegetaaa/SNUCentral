"""Entry point: P@K, Recall@K, MRR for BM25 vs TF-IDF on eval/queries.csv. Usage: python evaluate.py [-k 5]"""

import argparse
import csv
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from eval.metrics import precision_at_k, recall_at_k, reciprocal_rank, tune_threshold  # noqa: E402
from snu_central.config import load_config, project_path  # noqa: E402
from snu_central.index import read_chunks  # noqa: E402
from snu_central.retrieval import load_retriever  # noqa: E402
from snu_central.retrieval.gate import check  # noqa: E402


def make_typo(query: str) -> tuple[str, str, str]:
    """Swap two middle letters of the longest word: a deterministic, realistic typo."""
    word = max(re.findall(r"[A-Za-z]+", query), key=len)
    i = len(word) // 2
    typo = word[:i - 1] + word[i] + word[i - 1] + word[i + 1:]
    return query.replace(word, typo, 1), word.lower(), typo.lower()


def spelling_robustness(ret, queries, qrels, k) -> list[str]:
    """FR-4.11: does "Did you mean" restore a typo, and how much ranking quality does that recover?"""
    fixed, rr_typo, rr_fixed, n = 0, 0.0, 0.0, 0
    for q in queries:
        if q["answerable"] != "1":
            continue
        typo_q, word, typo = make_typo(q["query"])
        if typo == word:
            continue
        n += 1
        sug = ret.speller.suggest(typo_q)
        corrected = sug.text if sug else typo_q
        fixed += word in corrected.lower().split() or word in re.findall(r"[a-z]+", corrected.lower())
        rel = qrels[q["query_id"]]
        rr_typo += reciprocal_rank([c["chunk_id"] for c, _ in ret.search(typo_q, k)], rel)
        rr_fixed += reciprocal_rank([c["chunk_id"] for c, _ in ret.search(corrected, k)], rel)
    return ["\n== Spelling robustness (BM25, one swapped-letter typo per answerable query) ==",
            f"  typo restored by the speller: {fixed}/{n}",
            f"  MRR with the typo: {rr_typo / n:.3f}   after correction: {rr_fixed / n:.3f}"]


def gate_confusion(ans_conf, un_conf, tau, vocab_rejected) -> list[str]:
    """The abstention gate alone (before any LLM call) as a classifier; positive class = decline (eq. 13)."""
    tau = tau or 0.0
    tp = sum(c < tau for c in un_conf)              # unanswerable, declined
    fn = len(un_conf) - tp                          # unanswerable, passed on to the LLM
    fp = sum(c < tau for c in ans_conf)             # answerable, wrongly declined
    tn = len(ans_conf) - fp
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return [f"  gate at configured tau={tau:.2f}: TP={tp} FN={fn} FP={fp} TN={tn}  "
            f"accuracy={(tp + tn) / (tp + tn + fp + fn):.2f} precision={prec:.2f} recall={rec:.2f} F1={f1:.2f}"]


def retrieval_latency(ret, queries, k, repeats: int = 20) -> list[str]:
    """NFR-6.4: retrieval time per query (analysis + expansion + BM25 + top-K), warm index in memory."""
    times = []
    for q in queries:
        t0 = time.perf_counter()
        for _ in range(repeats):
            ret.search(q["query"], k)
        times.append((time.perf_counter() - t0) / repeats * 1000)
    times.sort()
    return ["\n== Retrieval latency (BM25, index in memory) ==",
            f"  median {times[len(times) // 2]:.1f} ms, max {times[-1]:.1f} ms per query (target < 500 ms)"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", type=int)
    k = ap.parse_args().k or load_config()["retrieval"]["top_k"]
    cfg = load_config()

    queries = list(csv.DictReader(open(ROOT / "eval/queries.csv", encoding="utf-8")))
    # Judgments were made before de-duplication: map a removed duplicate to the chunk that replaced it.
    canon = {d: c["chunk_id"] for c in read_chunks(project_path(cfg, "chunks")) for d in c.get("duplicate_ids", [])}
    qrels = defaultdict(set)
    for r in csv.DictReader(open(ROOT / "eval/qrels.csv", encoding="utf-8")):
        if int(r["relevance"]) > 0:
            qrels[r["query_id"]].add(canon.get(r["chunk_id"], r["chunk_id"]))

    out, summary, tops = [], {}, {}
    out.append(f"Retrieval evaluation, K={k}, {sum(q['answerable']=='1' for q in queries)} answerable queries")
    for ranker in ("tfidf", "bm25"):
        ret = load_retriever(cfg, ranker)
        P, R, F, M, per, ans_top, un_top, vocab_miss = [], [], [], [], [], [], [], 0
        for q in queries:
            res = ret.search(q["query"], k)
            ranked = [c["chunk_id"] for c, _ in res]
            top = ret.confidence(ret.query_terms(q["query"]), res[0][1]) if res else 0.0
            if q["answerable"] == "1":
                rel = qrels[q["query_id"]]
                p, r_, m = precision_at_k(ranked, rel, k), recall_at_k(ranked, rel, k), reciprocal_rank(ranked, rel)
                f1 = 2 * p * r_ / (p + r_) if p + r_ else 0.0
                P.append(p); R.append(r_); F.append(f1); M.append(m); ans_top.append(top)
                per.append(f"  {q['query_id']}  P@{k}={p:.2f}  R@{k}={r_:.2f}  F1={f1:.2f}  RR={m:.2f}  conf={top:.3f}  {q['query'][:50]}")
            else:
                un_top.append(top)
                reason = check(ret, q["query"], res, None).reason
                vocab_miss += reason == "no_known_terms"
                per.append(f"  {q['query_id']}  (unanswerable)  conf={top:.3f}  gate={reason}  {q['query'][:45]}")
        n = len(P)
        tau, acc = tune_threshold(ans_top, un_top)
        summary[ranker] = (sum(P) / n, sum(R) / n, sum(F) / n, sum(M) / n)
        tops[ranker] = (tau, acc)
        out.append(f"\n== {ranker.upper()} ==")
        out += per
        out.append(f"  unanswerable rejected by vocabulary check alone: {vocab_miss}/{len(un_top)}")
        out.append(f"  tuned tau={tau:.3f} (accuracy on answerable+unanswerable: {acc:.0%})")
        out += gate_confusion(ans_top, un_top, cfg["retrieval"]["abstain_threshold"], vocab_miss)

    out += spelling_robustness(load_retriever(cfg, "bm25"), queries, qrels, k)
    out += retrieval_latency(load_retriever(cfg, "bm25"), queries, k)
    out.append(f"\n{'Ranker':<8}{'P@'+str(k):>8}{'R@'+str(k):>8}{'F1@'+str(k):>8}{'MRR':>8}")
    for r, (p, rc, f1, m) in summary.items():
        out.append(f"{r:<8}{p:>8.3f}{rc:>8.3f}{f1:>8.3f}{m:>8.3f}")
    text = "\n".join(out)
    print(text)
    res_dir = ROOT / "eval/results"
    res_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (res_dir / f"retrieval-{stamp}.txt").write_text(text + "\n", encoding="utf-8")
    (res_dir / "latest.json").write_text(json.dumps(
        {"k": k, "metrics": {r: dict(zip(("P", "R", "F1", "MRR"), v)) for r, v in summary.items()},
         "tau": {r: t[0] for r, t in tops.items()}}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
