"""RAG answer generation (FR-5.x): retrieve -> gate -> prompt -> generate -> validate -> log."""

import json
import re
import time
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field

from ..config import load_config, project_path
from ..retrieval.gate import check as gate_check
from . import citations
from .prompt import build_messages
from .providers import LLMUnavailable, get_provider

NOT_COVERED = "This isn't covered in the documents I have."
# The prompt's refusal sentence and common decline phrasings: such answers need no citation.
DECLINED = re.compile(r"could not find this in the documents|can[’']?t help|cannot help|not about shiv nadar|"
                      r"only (answer|help)|outside the scope|isn[’']t covered|not covered in", re.I)


def is_declined(text: str) -> bool:
    """True for a short answer whose point is that the documents do not cover the question."""
    return bool(DECLINED.search(text)) and len(text.split()) < 60
FALLBACK_NOTE = "Answer generation is unavailable right now, here are the relevant sections."


@dataclass
class Answer:
    query: str
    status: str                    # answered | abstained | fallback
    text: str = ""
    results: list = field(default_factory=list)       # [(chunk, score)] sent as passages [1]..[k]
    citation: "citations.CitationCheck | None" = None
    reason: str = ""
    model: str | None = None
    notice: str | None = None      # e.g. model chosen automatically
    corrected_from: str | None = None   # what the user typed, when a spelling-corrected query was searched (FR-4.11)
    latency_s: float = 0.0
    first_token_s: float | None = None   # time until the first answer text appeared (NFR-6.4)


CONTACT_HINT = (" Try rephrasing, or ask the relevant office: Academic Affairs (courses, grades, attendance), "
                "Student Affairs (conduct, hostel, campus life), Finance Office (fees), Registrar (transcripts).")


def expand_context(results: list, retriever, n_top: int = 3, cap: int = 8) -> list:
    """Append the previous/next chunk of the best hits as extra passages (marked `_context`).

    Answers often sit in a table row or list item right next to the paragraph that matched
    (e.g. "minimum class size" -> the table with the numbers). Retrieval and its metrics are
    unchanged: the gate and evaluation only see the original results.
    """
    order = getattr(retriever, "_doc_order", None)
    if order is None:
        order = {}
        for c in retriever.chunks.values():                  # chunks.jsonl keeps document order
            order.setdefault(c["doc_id"], []).append(c["chunk_id"])
        retriever._doc_order = order
    have = {c["chunk_id"] for c, _ in results}
    cands: list[tuple[int, dict]] = []                       # (priority, neighbour chunk)
    for c, _ in results[:n_top]:
        ids = order[c["doc_id"]]
        i = ids.index(c["chunk_id"])
        for j in (i + 1, i - 1):                             # following chunk first: tables/lists continue forward
            if 0 <= j < len(ids):
                nb = retriever.chunks[ids[j]]
                if nb["section"] == c["section"]:
                    cands.append((0, nb))
                elif nb["page_number"] == c["page_number"]:  # e.g. definition on p.4, its table under the next heading
                    cands.append((1, nb))
    out = list(results)
    for _, nb in sorted(cands, key=lambda x: x[0]):          # stable: keeps rank order within a priority
        if nb["chunk_id"] not in have and len(out) < cap:
            have.add(nb["chunk_id"])
            out.append((dict(nb, _context=True), 0.0))
    return out


def answer_stream(query: str, retriever, cfg: dict | None = None, provider=None,
                  correct_spelling: bool = True) -> Iterator[str | Answer]:
    """Yield text pieces while the LLM streams, then finally the complete Answer object.

    Words that occur nowhere in the documents are replaced by their closest vocabulary word before
    searching (FR-4.11); `correct_spelling=False` searches the query exactly as typed."""
    cfg = cfg or load_config()
    t0 = time.time()
    k, tau = cfg["retrieval"]["top_k"], cfg["retrieval"]["abstain_threshold"]
    corrected_from = None
    if correct_spelling and (fix := retriever.speller.suggest(query)):
        corrected_from, query = query, fix.text       # the replaced words could not match anything as typed
    results = retriever.search(query, k)
    gate = gate_check(retriever, query, results, tau)

    if not gate.answer:                                   # no LLM call (FR-5.9)
        ans = Answer(query, "abstained", NOT_COVERED + CONTACT_HINT, results, reason=gate.reason)
        yield ans.text
    else:
        try:
            provider = provider or get_provider(cfg)
            if hasattr(provider, "notice") and not getattr(provider, "_auto_selected", False):
                provider.notice = None
            parts, first = [], None
            results = expand_context(results, retriever, cfg["retrieval"].get("context_top", 3),
                                     cfg["retrieval"].get("context_cap", 8))
            for piece in provider.stream(build_messages(query, results, cfg["llm"]["prompt_version"])):
                if first is None:
                    first = round(time.time() - t0, 2)
                parts.append(piece)
                yield piece
            text = citations.normalize("".join(parts)).strip()
            if not text:
                raise LLMUnavailable("empty answer")
            ans = Answer(query, "answered", text, results, citations.check(text, len(results)),
                         model=getattr(provider, "model_used", None),
                         notice=getattr(provider, "notice", None), first_token_s=first)
        except LLMUnavailable as e:                       # passages-only fallback (FR-5.12, NFR-1.7)
            ans = Answer(query, "fallback", FALLBACK_NOTE, results, reason=str(e))
            yield ans.text
    ans.corrected_from = corrected_from
    ans.latency_s = round(time.time() - t0, 2)
    _log(cfg, ans)
    yield ans


def answer_question(query: str, retriever, cfg: dict | None = None, provider=None,
                    correct_spelling: bool = True) -> Answer:
    last = None
    for item in answer_stream(query, retriever, cfg, provider, correct_spelling):
        last = item
    return last


_PII = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "<email>"),
        (re.compile(r"\b[A-Za-z]{0,4}\d{6,}\b"), "<id>"),        # roll / enrolment numbers
        (re.compile(r"\+?\d[\d\s-]{8,}\d"), "<number>")]          # phone numbers


def redact(text: str) -> str:
    """Strip emails, phone and roll numbers before anything is written to the log (NFR-9.1)."""
    for pat, rep in _PII:
        text = pat.sub(rep, text)
    return text


def _log(cfg: dict, ans: Answer) -> None:
    """One JSON line per query: no personal data, only the query text, chunk ids, scores, outcome (FR-8.7)."""
    path = project_path(cfg, "query_log")
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "query": redact(ans.query), "status": ans.status,
           "reason": ans.reason, "model": ans.model, "latency_s": ans.latency_s,
           "first_token_s": ans.first_token_s,
           "corrected_from": redact(ans.corrected_from) if ans.corrected_from else None,
           "chunks": [[c["chunk_id"], round(s, 3)] for c, s in ans.results],
           "answer": redact(ans.text) if ans.status == "answered" else "",
           "invalid_markers": ans.citation.invalid if ans.citation else []}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
