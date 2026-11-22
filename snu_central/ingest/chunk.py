"""Headings + paragraphs -> chunks with full citation metadata (FR-2.7, FR-2.8).

Paragraphs are PyMuPDF blocks, split wherever a heading line appears.
A line is a heading when it is short and either larger than body text,
bold, or starts with a section number ("5.2", "A1.", "SECTION A:").
Headings form a stack, so a chunk's `section` reads like
"SECTION A: GRADING SCALE > A1. Grading Scale".

Chunking: paragraphs shorter than `min_words` are merged with the following
paragraphs of the same section; paragraphs longer than `max_words` are split
at sentence boundaries. A chunk never crosses a section boundary.
"""

import re
from collections import Counter
from dataclasses import dataclass

from .clean import SKIP_SECTION, is_boilerplate, is_toc_page, normalize
from .extract import ExtractedDoc, Line

HEADING_MAX_WORDS = 12
NUMBERED = re.compile(
    r"^(?P<num>SECTION\s+[A-Z0-9]+\s*:?|(?:\d+\.)+\d*|\d+\)|[A-Z]\d+(?:\.\d+)*\.?|[A-Z]\.)"
    r"(?:\s+(?P<rest>\S.*)|(?<=\.)(?P<rest2>[A-Z].*))$"   # "1.DEPARTMENT" (no space) is also numbered
)
# "A1. Grading Scale: The current grading scale ..." -> heading "A1. Grading Scale", body after the colon
INLINE_HEADING = re.compile(r"^(?P<head>(?:[A-Z]\d+(?:\.\d+)*\.?|(?:\d+\.)+\d*)\s+[^:.]{2,60}):\s+(?P<body>\S.*)$")
BARE_NUMBER = re.compile(r"(SECTION\s+)?[A-Z]?[\d.]+:?|[A-Z]\.")   # "A1.", "5.2.", "SECTION 3:" alone on a line
PLAIN_NUM = re.compile(r"^((?:\d+\.)+\d*)\s")                    # "2. ", "4.1. ", "4.1 "
BULLET = re.compile(r"^[-•▪●o]\s")
SENTENCE_END = re.compile(r"(?<=[.!?;])\s+(?=[A-Z0-9(\"'])")
# A heading never ends on a word that needs a continuation ("... identified as", "... write to X for").
CONNECTOR_END = re.compile(
    r"\b(a|an|and|are|as|at|be|by|for|from|in|is|of|on|or|shall|that|the|to|which|will|with)$", re.I)


@dataclass
class Paragraph:
    page: int
    section: str
    text: str


def _level(text: str, size: float, body: float) -> int:
    """Heading depth: 1 = top level. Numbered headings use their numbering."""
    m = NUMBERED.match(text)
    if m:
        num = m.group("num").rstrip(".:) ").strip()
        if num.upper().startswith("SECTION"):
            return 1
        if re.fullmatch(r"[A-Z]", num):
            return 1
        if re.fullmatch(r"[A-Z]\d+(\.\d+)*", num):
            return 2 + num.count(".")
        return 1 + num.count(".")
    if size >= body + 3:
        return 1
    if size > body + 0.5:
        return 2
    return 3


SENTENCE_WORD = re.compile(r"\b(is|are|was|were|will|shall|must|should|may|can|not|has|have|be|been)\b", re.I)


def _reads_as_sentence(text: str) -> bool:
    """Unstyled numbered lines such as "2. Tuition Fee Waiver not applicable for Sponsored Candidates" (an item
    under "Notes") are list items, not section titles: real headings almost never contain a verb or negation."""
    return bool(PLAIN_NUM.match(text)) and bool(SENTENCE_WORD.search(text))


def _is_heading(line: Line, body: float, continuing: bool, alone: bool) -> bool:
    """`continuing`: the previous line of this paragraph ended mid-sentence.
    `alone`: the line is a PyMuPDF block on its own (typical for headings)."""
    text = line.text
    words = text.split()
    if not words or len(words) > HEADING_MAX_WORDS or BULLET.match(text) or text[0].islower():
        return False
    larger = line.size > body + 0.5
    if continuing and not larger:
        return False
    if text.endswith((".", ",", ";")) and not BARE_NUMBER.fullmatch(text):   # sentences are not headings
        return False
    if " | " in text or not re.search(r"[A-Za-z]{3}", text):   # table rows, bare numbers
        return False
    if CONNECTOR_END.search(text.rstrip(":")):
        return False
    if larger or line.bold:
        return True
    m = NUMBERED.match(text)
    return bool(m) and alone and len(words) <= 10 and (m.group("rest") or m.group("rest2"))[:1].isupper()


def paragraphs(doc: ExtractedDoc) -> list[Paragraph]:
    out: list[Paragraph] = []
    stack: list[tuple[int, str]] = []          # (level, heading text)

    def section() -> str:
        return " > ".join(h for _, h in stack)

    def push(text: str, line: Line) -> None:
        lvl = _level(text, line.size, doc.body_size)
        # Inside a "SECTION A:" / "A1." scheme, plain numbers ("8. ...") are list items, not chapters.
        if re.match(r"^\d", text) and any(h.upper().startswith("SECTION") for _, h in stack):
            lvl += 2
        while stack and stack[-1][0] >= lvl:
            stack.pop()
        stack.append((lvl, normalize(text)))

    for page in doc.pages:
        if is_toc_page(page):
            continue
        buf: list[str] = []
        block = None
        lines_per_block = Counter(l.block for l in page.lines)

        def flush():
            if buf:
                text = normalize(" ".join(buf))
                if text and not is_boilerplate(text) and not SKIP_SECTION.match(stack[0][1] if stack else ""):
                    out.append(Paragraph(page.number, section(), text))
                buf.clear()

        for line in page.lines:
            if line.block != block:
                flush()
                block = line.block
            inline = INLINE_HEADING.match(line.text)
            if inline and len(inline.group("head").split()) <= 6:
                flush()
                push(inline.group("head"), line)
                buf.append(inline.group("body"))
            elif _is_heading(line, doc.body_size,
                             continuing=bool(buf) and not buf[-1].rstrip().endswith((".", ":", "?", "!", ";")),
                             alone=lines_per_block[line.block] == 1) \
                    and (line.bold or line.size > doc.body_size + 0.5 or not _reads_as_sentence(line.text)):
                flush()
                push(line.text, line)
            else:
                buf.append(line.text)
        flush()
    return out


def _split_long(text: str, max_words: int) -> list[str]:
    if len(text.split()) <= max_words:
        return [text]
    pieces, cur = [], []
    for sent in SENTENCE_END.split(text):
        words = sent.split()
        if cur and len(cur) + len(words) > max_words:
            pieces.append(" ".join(cur))
            cur = []
        # a single "sentence" longer than max_words (e.g. a long table) is cut by words
        while len(words) > max_words:
            pieces.append(" ".join(words[:max_words]))
            words = words[max_words:]
        cur.extend(words)
    if cur:
        pieces.append(" ".join(cur))
    return pieces


def make_chunks(doc_row: dict, paras: list[Paragraph], min_words: int, max_words: int) -> list[dict]:
    """Group paragraphs into chunks and attach the document's metadata."""
    groups: list[tuple[int, int, str, str]] = []       # (page_start, page_end, section, text)
    cur: list[Paragraph] = []

    def emit():
        if cur:
            text = " ".join(p.text for p in cur)
            for piece in _split_long(text, max_words):
                groups.append((cur[0].page, cur[-1].page, cur[0].section, piece))
            cur.clear()

    for p in paras:
        if cur and p.section != cur[0].section:
            emit()
        cur.append(p)
        if sum(len(x.text.split()) for x in cur) >= min_words:
            emit()
    emit()

    # A short tail left alone in its section is merged into the previous chunk of that section.
    merged: list[tuple[int, int, str, str]] = []
    for g in groups:
        if merged and len(g[3].split()) < min_words // 2 and merged[-1][2] == g[2] \
                and len(merged[-1][3].split()) + len(g[3].split()) <= max_words:
            ps, _, sec, text = merged[-1]
            merged[-1] = (ps, g[1], sec, f"{text} {g[3]}")
        else:
            merged.append(g)

    chunks, per_page = [], {}
    for page_start, page_end, sec, text in merged:
        n = per_page[page_start] = per_page.get(page_start, 0) + 1
        chunks.append({
            "chunk_id": f"{doc_row['doc_id']}_p{page_start:03d}_{n:02d}",
            "doc_id": doc_row["doc_id"],
            "document_name": doc_row["title"],
            "file_name": doc_row["file_path"].rsplit("/", 1)[-1],
            "file_path": doc_row["file_path"],
            "source_url": doc_row["source_url"],
            "category": doc_row["category"],
            "department": doc_row["department"],
            "page_number": page_start,
            "page_end": page_end,
            "section": sec,
            "paragraph_id": f"P{n}",
            "text": text,
            "word_count": len(text.split()),
            "publication_date": doc_row.get("publication_date", ""),
            "effective_date": doc_row["effective_date"],
            "date_source": doc_row.get("date_source", ""),
            "is_superseded": doc_row["is_superseded"] == "true",
            "fetched_at": doc_row["fetched_at"],
        })
    return chunks
