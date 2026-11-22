"""Data passed between the source-specific fetchers and the fetch pipeline."""

from dataclasses import dataclass, field


@dataclass
class FetchedDoc:
    """A document downloaded from a source, before it is written to disk."""

    doc_id: str            # stable across runs, e.g. "S1_ug_handbook", "S4_node719"
    source_id: str         # S1..S4
    title: str
    url: str               # page or file the document came from
    filename: str          # name to save under static/documents/<category>/
    data: bytes
    folder: str = ""       # S4 tree path, e.g. "Student Academic Policies"
    category: str = ""     # per-document override from sources.yaml (else rules/default)
    department: str = ""   # per-document override from sources.yaml


@dataclass
class FetchFailure:
    source_id: str
    url: str
    error: str
    doc_id: str = ""       # set when we know which document failed


@dataclass
class SourceResult:
    docs: list[FetchedDoc] = field(default_factory=list)
    failures: list[FetchFailure] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # login-only pages (NFR-2.4), non-PDF files
