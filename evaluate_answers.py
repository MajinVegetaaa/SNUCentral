"""Answer-quality evaluation (FR-8.4, FR-8.5): runs every eval query through the FULL pipeline.

Usage: python evaluate_answers.py [--pause 22]   (22 s keeps ~2.5k-token calls under Groq's 8k tokens/min)

Writes eval/results/answers-<timestamp>.csv. Automatic columns: status, citation validity, abstention.
Blank columns (correct, supported, citation_ok, complete) are for MANUAL grading, 0/1 each, per the
five criteria of the project brief (§3.7B). Then run:  python evaluate_answers.py --summarize <file.csv>
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from snu_central.config import load_config  # noqa: E402
from snu_central.generation import answer_question, expand_context, is_declined  # noqa: E402
from snu_central.generation.providers import get_provider  # noqa: E402
from snu_central.retrieval import load_retriever  # noqa: E402
from snu_central.textproc.analyzer import analyze  # noqa: E402

_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def unsupported_numbers(answer: str, results) -> list[str]:
    """Numbers stated in the answer that occur in none of the passages sent: a cheap groundedness check (NFR-1.1).
    Citation markers like [3] are ignored."""
    source = " ".join(f'{c["document_name"]} {c["section"]} {c.get("effective_date", "")} {c["text"]}'
                      for c, _ in results).replace(",", "")
    body = re.sub(r"\[\d+\]", "", answer)
    return sorted({n for n in _NUM.findall(body) if n.replace(",", "") not in source})


FIELDS = ["query_id", "query", "answerable", "status", "abstained", "answer", "valid_markers", "invalid_markers", "unsupported_numbers",
          "uncited_sentences", "cited_sources", "passages", "model", "prompt_version", "first_token_s", "latency_s",
          "correct", "supported", "citation_ok", "complete", "notes"]


# ---- statement-level groundedness (NFR-1.1) ---------------------------------------------------------
_MARK = re.compile(r"\[(\d+)\]")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
SUPPORT_FLAG = 0.6       # statements whose content words are < 60% found in their cited passages get flagged
STATEMENT_FIELDS = ["query_id", "statement_no", "statement", "kind", "own_markers", "markers_used", "word_support",
                    "flag", "supported", "notes"]


_ABSENCE = re.compile(r"\b(do(es)? not|don[’']t|no)\b.{0,40}\b(specify|provide|list|detail|mention|state|cover|contain|include)|"
                      r"\bnot (specified|covered|stated|detailed|mentioned)\b|could not find", re.I)


def split_statements(answer: str) -> list[tuple[str, list[int], str]]:
    """(statement, markers, how) for every claim of an answer; how = "own" | "list" | "none" | "absence".

    Lines are bullets, numbered steps or sentences. Headings (a short line that is not a list item,
    has no marker and no closing punctuation, e.g. "**Exceptions**") are skipped. A statement without
    a marker takes the marker of the next statement that has one, because the model often cites a
    whole list once at its end. Older answer files stored line breaks as runs of spaces."""
    lines = [l for l in re.split(r"\n|\s{2,}", answer) if l.strip()]
    items = []
    for line in lines:
        is_item = bool(_BULLET.match(line))
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z*])", _BULLET.sub("", line).strip()):
            marks = [int(m) for m in _MARK.findall(sent)]
            plain = re.sub(r"[*_`#]", "", _MARK.sub("", sent)).strip(" .;")
            words = plain.split()
            if len(words) < (2 if is_item else 3) or plain.endswith(":"):     # "- Marks reduction" is a claim
                continue
            if not is_item and not marks and not re.search(r"[.!?]\s*$", sent.strip()) and len(words) <= 10:
                continue                                    # a heading such as "Procedure for lateral entry"
            items.append((plain, marks))
    out = []
    for i, (plain, marks) in enumerate(items):
        if _ABSENCE.search(plain):
            out.append((plain, marks, "absence"))
        elif marks:
            out.append((plain, marks, "own"))
        else:
            later = next((m for _, m in items[i + 1:] if m), [])
            out.append((plain, later, "list" if later else "none"))
    return out


def word_support(statement: str, passages: list[dict]) -> float:
    """Share of the statement's content words (same analyzer as the index) found in the given passages."""
    words = set(analyze(statement))
    if not words:
        return 1.0
    source = set()
    for c in passages:
        source |= set(analyze(f'{c["document_name"]} {c["section"]} {c["text"]}'))
    return len(words & source) / len(words)


def write_statements(answers_csv: Path) -> Path:
    """Split every answer of a run into statements and pre-check each against the passages it cites."""
    cfg = load_config()
    ret = load_retriever(cfg)
    r = cfg["retrieval"]
    out = answers_csv.with_name(answers_csv.name.replace("answers-", "statements-"))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, STATEMENT_FIELDS)
        w.writeheader()
        for row in csv.DictReader(open(answers_csv, encoding="utf-8")):
            if row["status"] != "answered" or row["abstained"] == "1":
                continue
            query = row["query"]
            res = expand_context(ret.search(query, r["top_k"]), ret, r["context_top"], r["context_cap"])
            if len(res) != row["passages"].count("["):
                raise RuntimeError(f"{row['query_id']}: passages differ from the run; re-run evaluate_answers.py")
            for i, (text, marks, how) in enumerate(split_statements(row["answer"]), 1):
                cited = [res[m - 1][0] for m in marks if 1 <= m <= len(res)]
                ws = word_support(text, cited) if cited else 0.0
                flag = ("" if how == "absence" else "no citation" if not marks
                        else "low word support" if ws < SUPPORT_FLAG else "")
                w.writerow({"query_id": row["query_id"], "statement_no": i, "statement": text, "kind": how,
                            "own_markers": " ".join(map(str, marks)) if how == "own" else "",
                            "markers_used": " ".join(map(str, marks)), "word_support": f"{ws:.2f}",
                            "flag": flag, "supported": "", "notes": ""})
    return out


def summarize_statements(path: Path) -> str:
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    n = len(rows)
    if not n:
        return "No statements."
    pct = lambda a, b: f"{a}/{b} = {a / b:.0%}" if b else "n/a"  # noqa: E731
    graded = [x for x in rows if x["supported"] in ("0", "1")]
    lines = [f"Statement-level groundedness: {path.name}  ({n} statements in {len({x['query_id'] for x in rows})} answers)",
             "  with their own citation marker:      " + pct(sum(bool(x["own_markers"]) for x in rows), n),
             "  covered by a marker (own or list's): " + pct(sum(bool(x["markers_used"]) for x in rows), n),
             "  'not in the documents' statements:   " + pct(sum(x.get("kind") == "absence" for x in rows), n),
             f"  word support >= {SUPPORT_FLAG:.0%} in cited passages: " + pct(sum(not x["flag"] for x in rows), n),
             "  flagged for review: " + ", ".join(f"{x['query_id']}#{x['statement_no']}" for x in rows if x["flag"])]
    auto = sum("auto-pass" in x.get("notes", "") for x in graded)
    if graded and auto:
        lines.append(f"  graded by reading: {len(graded) - auto}; auto-pass (cited, word support >= {SUPPORT_FLAG:.0%}): {auto}")
    lines.append("  SUPPORTED (NFR-1.1 target >= 90%; uncited statements count as unsupported): "
                 + (pct(sum(x["supported"] == "1" for x in graded), len(graded)) + f" ({len(graded)}/{n} graded)"
                    if graded else "not graded yet: fill the 'supported' column with 0/1"))
    return "\n".join(lines)


def run(pause: float) -> Path:
    cfg = load_config()
    ret = load_retriever(cfg)
    provider = get_provider(cfg)
    queries = list(csv.DictReader(open(ROOT / "eval/queries.csv", encoding="utf-8")))
    out = ROOT / "eval/results" / f"answers-{time.strftime('%Y%m%d-%H%M%S')}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        for i, q in enumerate(queries):
            ans = None
            for attempt in range(3):                       # a rate-limit fallback is retried, not graded
                ans = answer_question(q["query"], ret, cfg, provider)
                if ans.status != "fallback":
                    break
                print(f"  {q['query_id']}: LLM unavailable ({ans.reason[:60]}), waiting 30 s")
                time.sleep(30)
            cit = ans.citation
            cited = [f"[{n}] {ans.results[n-1][0]['document_name']} p.{ans.results[n-1][0]['page_number']}"
                     for n in (cit.valid if cit else [])]
            refused = ans.status == "abstained" or (ans.status == "answered" and is_declined(ans.text))
            w.writerow({
                "query_id": q["query_id"], "query": q["query"], "answerable": q["answerable"], "status": ans.status,
                "abstained": int(refused), "answer": ans.text,
                "valid_markers": " ".join(map(str, cit.valid)) if cit else "",
                "invalid_markers": " ".join(map(str, cit.invalid)) if cit else "",
                "unsupported_numbers": " ".join(unsupported_numbers(ans.text, ans.results)) if ans.status == "answered" else "",
                "uncited_sentences": cit.uncited_sentences if cit else "",
                "cited_sources": " | ".join(cited),
                "passages": " | ".join(f"[{n}] {c['document_name']} p.{c['page_number']}"
                                       for n, (c, _) in enumerate(ans.results, 1)),
                "model": ans.model or "", "prompt_version": cfg["llm"]["prompt_version"],
                "first_token_s": ans.first_token_s if ans.first_token_s is not None else "",
                "latency_s": ans.latency_s})
            f.flush()
            print(f"{q['query_id']} {ans.status:9} abstained={int(refused)} {q['query'][:60]}")
            if i < len(queries) - 1 and ans.status == "answered":
                time.sleep(pause)                          # stay under Groq's free-tier tokens/minute
    return out


def summarize(path: Path) -> str:
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    ans = [r for r in rows if r["answerable"] == "1"]
    un = [r for r in rows if r["answerable"] == "0"]
    lines = [f"Answer evaluation: {path.name}", f"answerable={len(ans)} unanswerable={len(un)}"]
    pct = lambda a, b: f"{a}/{b} = {a / b:.0%}" if b else "n/a"  # noqa: E731
    lines.append("Correct abstention on unanswerable: " + pct(sum(r["abstained"] == "1" for r in un), len(un)))
    lines.append("False abstention on answerable:     " + pct(sum(r["abstained"] == "1" for r in ans), len(ans)))
    answered = [r for r in ans if r["abstained"] == "0"]
    models = sorted({r["model"] for r in answered if r.get("model")})
    lines.append(f"Models that answered: {', '.join(models) or 'none'}"
                 + ("   <- fallback used: results do not measure the configured model" if len(models) > 1 else ""))
    lines.append("Answers with >=1 valid citation:    " + pct(sum(bool(r["valid_markers"]) for r in answered), len(answered)))
    lines.append("Answers with an invalid marker:     " + pct(sum(bool(r["invalid_markers"]) for r in answered), len(answered)))
    if answered and "unsupported_numbers" in answered[0]:
        flagged = [r["query_id"] for r in answered if r["unsupported_numbers"]]
        lines.append("Answers with a number not in passages: " + pct(len(flagged), len(answered)) + (f" {flagged}" if flagged else ""))
    lat = sorted(float(r["latency_s"]) for r in answered if r["latency_s"])
    ftt = sorted(float(r["first_token_s"]) for r in answered if r.get("first_token_s"))
    if lat:
        lines.append(f"Full answer time: median {lat[len(lat)//2]:.1f}s, max {lat[-1]:.1f}s (target ~5 s)")
    if ftt:
        lines.append(f"First answer text: median {ftt[len(ftt)//2]:.1f}s, max {ftt[-1]:.1f}s (target ~3 s)")
    for col, name in [("correct", "Factual correctness"), ("supported", "Evidence support"),
                      ("citation_ok", "Citation accuracy"), ("complete", "Completeness")]:
        graded = [r for r in answered if r[col] in ("0", "1")]
        lines.append(f"{name:<20} " + (pct(sum(r[col] == "1" for r in graded), len(graded)) + f" ({len(graded)} graded)"
                                        if graded else "not graded yet"))
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pause", type=float, default=22, help="seconds between LLM calls (free-tier tokens/min)")
    ap.add_argument("--summarize", type=Path, help="summarize an already graded answers CSV")
    ap.add_argument("--statements", type=Path,
                    help="answers CSV -> statements CSV for statement-level grading (NFR-1.1); summarizes it if it is one")
    a = ap.parse_args()
    if a.statements:
        sp = a.statements if a.statements.name.startswith("statements-") else write_statements(a.statements)
        print(summarize_statements(sp) + f"\n\nFile: {sp}")
        sys.exit(0)
    path = a.summarize or run(a.pause)
    if not a.summarize:
        sp = write_statements(path)
        print("\n" + summarize_statements(sp) + f"\nStatements file: {sp}")
    print("\n" + summarize(path) + f"\n\nFile: {path}")
