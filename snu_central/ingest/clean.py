"""Remove layout noise and normalise text (FR-2.4).

* Running headers/footers: lines in the top/bottom page margin that repeat
  on many pages (digits ignored), plus page-number lines. Only margin lines
  are considered, so repeated table cells ("Item", "Year 1") are kept.
* Table-of-contents pages: many dot-leader lines.
* Boilerplate: copyright / "exclusive use" notices.
"""

import re
import unicodedata
from collections import Counter

from .extract import Page

TOP_MARGIN, BOTTOM_MARGIN = 0.08, 0.90
PAGE_NUMBER = re.compile(r"^(page\s*)?\d+(\s*(of|/)\s*\d+)?$", re.I)
DOT_LEADER = re.compile(r"\.{6,}|(\.\s){5,}|…{3,}")
BOILERPLATE = re.compile(
    r"all rights reserved|meant for (the )?exclusive use|no part of the document may be"
    r"|without prior written permission|stored in any retrieval system|transmitted in any form",
    re.I,
)
TOC_MIN_LINES = 3
# Document-control tables on policy cover pages (versions, approvers), not policy content.
SKIP_SECTION = re.compile(r"^(release control|revision history|document control|version history|amendment history)",
                          re.I)


def _shape(text: str) -> str:
    """Text with digits masked, so 'Page 3 of 11' and 'Page 4 of 11' match."""
    return re.sub(r"\d+", "#", text.lower()).strip()


def _in_margin(line) -> bool:
    return line.y1 <= TOP_MARGIN + 0.02 or line.y0 >= BOTTOM_MARGIN


def strip_headers_footers(pages: list[Page], ratio: float) -> None:
    """Remove running headers/footers in place."""
    counts: Counter[str] = Counter()
    for page in pages:
        counts.update({_shape(l.text) for l in page.lines if _in_margin(l)})
    min_pages = max(2, int(len(pages) * ratio)) if len(pages) > 2 else len(pages) + 1
    repeated = {shape for shape, n in counts.items() if n >= min_pages}

    for page in pages:
        page.lines = [
            l for l in page.lines
            if not (_in_margin(l) and (_shape(l.text) in repeated or PAGE_NUMBER.match(l.text.strip())))
        ]


def is_toc_page(page: Page) -> bool:
    return sum(1 for l in page.lines if DOT_LEADER.search(l.text)) >= TOC_MIN_LINES


def is_boilerplate(text: str) -> bool:
    return bool(BOILERPLATE.search(text))


def normalize(text: str) -> str:
    """Unicode, quotes, bullets and whitespace. Keeps numbers, dates, ₹ and policy codes."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[•●▪■‣⁃]", "-", text)   # bullets -> "-"
    text = re.sub(r"(\w)-\s+([a-z])", r"\1\2", text)          # re-join words hyphenated across lines
    text = re.sub(r"(\s*\|\s*)+\|", " |", text)               # collapse empty table cells
    text = re.sub(r"\s+", " ", text)
    return text.strip(" |")
