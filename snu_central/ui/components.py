"""Source cards, PDF-at-page links, date warnings, abstention and fallback messages (FR-6.x, FR-7.x)."""

import re
from datetime import date

import streamlit as st

from ..textproc.analyzer import analyze

EXAMPLES = [
    "What is the minimum attendance required for UG students?",
    "How can I change my major?",
    "Can UG students work part time on campus?",
    "What is the tuition fee refund policy if I withdraw?",
    "What are the criteria for the Dean's List?",
    "How do I file a grievance?",
]

_WORD = re.compile(r"[A-Za-z0-9]+(?:[-./'][A-Za-z0-9]+)*")


def pdf_url(chunk: dict) -> str:
    """Streamlit serves ./static at /app/static/ (enableStaticServing). Chrome honours #page=N (FR-6.3)."""
    return f"/app/{chunk['file_path']}#page={chunk['page_number']}"


def doc_date(chunk: dict) -> str:
    return (chunk.get("effective_date") or chunk.get("publication_date") or "")[:10]


def date_warning(chunk: dict, stale_after_years: int) -> str | None:
    """Warn on superseded documents and on documents older than the configured age (FR-6.6)."""
    if str(chunk.get("is_superseded", "")).lower() in ("true", "1", "yes"):
        return "This document is marked as superseded. Check for a newer version."
    d = doc_date(chunk)
    if d:
        try:
            parsed = date.fromisoformat(d if len(d) == 10 else f"{d[:7]}-01")     # "2024-07" = July 2024
        except ValueError:
            return None
        if (date.today() - parsed).days > 365 * stale_after_years:
            return (f"Last revised {d}, more than {stale_after_years} years ago. "
                    "Check with the issuing office that this is still the current version.")
    return None


def highlight(text: str, query_terms: set[str]) -> str:
    """Bold words whose stem matches a query term (FR-7.10). Escapes markdown-significant characters first."""
    def sub(m: re.Match) -> str:
        w = m.group(0)
        return f"**{w}**" if set(analyze(w)) & query_terms else w
    safe = text.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_").replace("$", "\\$").replace("#", "\\#")
    return _WORD.sub(sub, safe)


def source_card(n: int, chunk: dict, score: float, query_terms: set[str], stale_years: int, cited: bool) -> None:
    with st.container(border=True):
        ctx = chunk.get("_context")
        tag = ":green-badge[cited]" if cited else (":gray-badge[adjacent section]" if ctx else ":gray-badge[retrieved]")
        st.markdown(f"**[{n}] {chunk['document_name']}** {tag}")
        meta = f"Page {chunk['page_number']}"
        if chunk.get("section"):
            meta += f" · {chunk['section']}"
        meta += f" · paragraph {chunk['paragraph_id']}" + (f" · {chunk['department']}" if chunk.get("department") else "")
        meta += f" · dated {doc_date(chunk)}" if doc_date(chunk) else " · date not stated"
        if not ctx:
            meta += f" · match {score:.2f}"
        st.caption(meta)
        warn = date_warning(chunk, stale_years)
        if warn:
            st.warning(warn, icon=":material/schedule:")
        st.markdown(highlight(chunk["text"], query_terms))
        st.link_button("Open PDF at this page", pdf_url(chunk), icon=":material/open_in_new:")


def render_sources(results, query_terms: set[str], cited: list[int], stale_years: int, title: str,
                   expanded: bool | None = None) -> None:
    """Cited passages are shown; the rest sit in an expander (open when nothing was cited, unless `expanded`)."""
    cited_set = set(cited)
    first = [(i, c, s) for i, (c, s) in enumerate(results, 1) if i in cited_set]
    rest = [(i, c, s) for i, (c, s) in enumerate(results, 1) if i not in cited_set]
    for i, c, s in first:
        source_card(i, c, s, query_terms, stale_years, True)
    if rest:
        with st.expander(f"{title} ({len(rest)})", expanded=(not first) if expanded is None else expanded):
            for i, c, s in rest:
                source_card(i, c, s, query_terms, stale_years, False)


def department_note(results, cited: list[int]) -> str | None:
    """Short 'verify with the issuing department' note (FR-6.7)."""
    pool = [results[i - 1][0] for i in cited if 1 <= i <= len(results)] or [c for c, _ in results[:1]]
    deps = list(dict.fromkeys(c["department"] for c in pool if c.get("department")))
    return f"Please verify with: {', '.join(deps)}." if deps else None
