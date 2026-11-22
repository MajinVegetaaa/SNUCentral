"""PDF -> pages of text lines with layout info (FR-2.1, FR-2.2).

PyMuPDF splits a page into blocks (roughly paragraphs or table rows), blocks
into lines, lines into spans (runs of one font). We keep, per line: text,
font size, bold flag, vertical position and block number. Lines on the same
baseline anywhere on the page (table cells often sit in separate blocks;
"F." + "Examination Stationery") are merged into one line, cells joined by " | ".
"""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

LIST_MARKER_MAX = 4   # "F.", "1.", "A1." - joined to the next cell with a space, not " | "


@dataclass
class Line:
    text: str
    size: float
    bold: bool
    y0: float      # top, as a fraction of page height (0 = top)
    y1: float      # bottom, as a fraction of page height
    block: int


@dataclass
class Page:
    number: int                     # 1-based, as printed in citations
    lines: list[Line] = field(default_factory=list)


@dataclass
class ExtractedDoc:
    pages: list[Page]
    body_size: float                # most common font size, weighted by characters


def _is_bold(span: dict) -> bool:
    return bool(span["flags"] & 16) or "bold" in span["font"].lower()


def extract(pdf_path: Path) -> ExtractedDoc:
    pages: list[Page] = []
    sizes: Counter[float] = Counter()

    with pymupdf.open(pdf_path) as doc:
        for pno, pdf_page in enumerate(doc, start=1):
            height = pdf_page.rect.height or 1.0
            page = Page(pno)
            raw = []
            for bno, block in enumerate(pdf_page.get_text("dict")["blocks"]):
                if block.get("type") != 0:          # skip images
                    continue
                for line in block["lines"]:
                    spans = [s for s in line["spans"] if s["text"].strip()]
                    if not spans:
                        continue
                    text = "".join(s["text"] for s in line["spans"]).strip()
                    size = round(max(s["size"] for s in spans), 1)
                    bold = all(_is_bold(s) for s in spans)
                    for s in spans:
                        sizes[round(s["size"], 1)] += len(s["text"].strip())
                    x0, y0, _, y1 = line["bbox"]
                    raw.append((y0, x0, text, size, bold, y0 / height, y1 / height, bno))

            # merge lines on the same baseline (within 2pt), left to right
            raw.sort(key=lambda r: (round(r[0]), r[1]))
            for y0, _, text, size, bold, fy0, fy1, bno in raw:
                prev = page.lines[-1] if page.lines else None
                if prev is not None and abs(prev.y0 * height - y0) <= 2:
                    sep = " " if len(prev.text) <= LIST_MARKER_MAX else " | "
                    prev.text = f"{prev.text}{sep}{text}"
                    prev.size = max(prev.size, size)
                    prev.bold = prev.bold and bold
                    prev.y1 = max(prev.y1, fy1)
                else:
                    page.lines.append(Line(text, size, bold, fy0, fy1, bno))
            pages.append(page)

    body_size = sizes.most_common(1)[0][0] if sizes else 10.0
    return ExtractedDoc(pages, body_size)
