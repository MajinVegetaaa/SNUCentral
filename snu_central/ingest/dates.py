"""Document dates for citations and staleness warnings (FR-2.8, FR-6.6).

Only dates the document itself states are used, never a guess:
  1. the "Release Control" table that SNU policies carry on page 2: the latest release date
     (or the ratification date when the release-date cell is empty),
  2. an explicit "Effective Date: ...", "effective from ...", "with effect from ..." line,
  3. "APPROVED BY ... IN <Month YYYY>" (month precision).
Anything else stays empty and the UI shows "date not stated" (NFR-1.4: decline rather than guess).
Hand overrides live in document_dates.yaml; a value typed into manifest.csv wins over both.
"""

import re
from datetime import date
from pathlib import Path

import pymupdf

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_DAY_MON_YEAR = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?[\s-]+({_MON})[,.\s-]+(\d{{4}})\b", re.I)
_MON_DAY_YEAR = re.compile(rf"\b({_MON})\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.I)
_NUMERIC = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2}|\d{4})\b")          # Indian order: dd.mm.yyyy
_MON_YEAR = re.compile(rf"\b({_MON})[,\s]+(\d{{4}})\b", re.I)

_RELEASE = re.compile(r"release\s+control|release\s+versions", re.I)
_RELEASE_END = re.compile(r"assured\s+by|ratified\s+by", re.I)
_EFFECTIVE = re.compile(r"effective\s+date\s*:?|effective\s+from|with\s+effect\s+from|w\.e\.f\.?", re.I)
_APPROVED_IN = re.compile(rf"approved\s+by\s+.{{0,80}}?\s+in\s+({_MON})\s+(\d{{4}})", re.I)


def _valid(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d) if 2000 <= y <= 2100 else None
    except ValueError:
        return None


def find_dates(text: str) -> list[date]:
    """Every full date (day, month, year) in `text`, in order of appearance."""
    found: list[tuple[int, date]] = []
    for m in _DAY_MON_YEAR.finditer(text):
        if d := _valid(int(m[3]), _MONTHS[m[2][:3].lower()], int(m[1])):
            found.append((m.start(), d))
    for m in _MON_DAY_YEAR.finditer(text):
        if d := _valid(int(m[3]), _MONTHS[m[1][:3].lower()], int(m[2])):
            found.append((m.start(), d))
    for m in _NUMERIC.finditer(text):
        y = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        if d := _valid(y, int(m[2]), int(m[1])):
            found.append((m.start(), d))
    return [d for _, d in sorted(found, key=lambda x: x[0])]


def date_from_text(pages: list[str]) -> tuple[str, str]:
    """(ISO date or "", evidence) from the text of the first pages of a document."""
    for no, text in enumerate(pages, 1):
        if m := _RELEASE.search(text):
            region = text[m.end():]
            if end := _RELEASE_END.search(region):
                region = region[:end.start()]
            if dates := find_dates(region):
                latest = max(dates)
                return latest.isoformat(), f"latest release in the Release Control table (p.{no})"
            if (rat := re.search(r"ratified\s+by", text, re.I)) and (dates := find_dates(text[rat.end():])):
                return max(dates).isoformat(), f"policy ratification date, release date left blank (p.{no})"
    for no, text in enumerate(pages, 1):
        for m in _EFFECTIVE.finditer(text):
            if dates := find_dates(text[m.end():m.end() + 40]):
                return dates[0].isoformat(), f'"{m.group(0).strip()} ..." (p.{no})'
            if mm := _MON_YEAR.match(text[m.end():m.end() + 25].strip()):
                return f"{int(mm[2]):04d}-{_MONTHS[mm[1][:3].lower()]:02d}", f'"{m.group(0).strip()} {mm[0]}" (p.{no})'
    for no, text in enumerate(pages, 1):
        if m := _APPROVED_IN.search(text):
            return f"{int(m[2]):04d}-{_MONTHS[m[1][:3].lower()]:02d}", f'"approved ... in {m[1]} {m[2]}" (p.{no})'
    return "", ""


def document_date(pdf_path: Path, max_pages: int = 3) -> tuple[str, str]:
    with pymupdf.open(pdf_path) as doc:
        pages = [" ".join(doc[i].get_text().split()) for i in range(min(max_pages, len(doc)))]
    return date_from_text(pages)
