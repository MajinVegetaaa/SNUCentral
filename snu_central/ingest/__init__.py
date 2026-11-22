"""PDF -> cleaned paragraph chunks with metadata (FR-2.x).

run_ingest() reads the active documents from the manifest and writes
processed_data/chunks.jsonl (one JSON object per chunk).
"""

import json
from dataclasses import dataclass, field

import yaml

from ..config import PROJECT_ROOT, project_path
from ..fetch.manifest import active_documents, read_manifest
from .chunk import make_chunks, paragraphs
from .clean import strip_headers_footers
from .dates import document_date
from .extract import extract


@dataclass
class IngestReport:
    documents: int = 0
    chunks: int = 0
    words: int = 0
    per_doc: list[tuple[str, int, int, str]] = field(default_factory=list)   # (title, pages, chunks, date)
    undated: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_ingest(cfg: dict) -> IngestReport:
    ch = cfg["chunking"]
    rows = active_documents(read_manifest(project_path(cfg, "manifest")), PROJECT_ROOT)
    out_path = project_path(cfg, "chunks")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = IngestReport()
    overrides_path = project_path(cfg, "document_dates")
    overrides = (yaml.safe_load(open(overrides_path, encoding="utf-8")) or {}) if overrides_path.exists() else {}

    with open(out_path, "w", encoding="utf-8") as out:
        for row in sorted(rows, key=lambda r: r["doc_id"]):
            try:
                row = dict(row, **resolve_date(row, overrides))
                doc = extract(PROJECT_ROOT / row["file_path"])
                strip_headers_footers(doc.pages, ch["header_footer_ratio"])
                chunks = make_chunks(row, paragraphs(doc), ch["min_words"], ch["max_words"])
            except Exception as e:  # noqa: BLE001 - one bad PDF must not stop the build
                report.errors.append(f"{row['doc_id']}: {e}")
                continue
            if not chunks:
                report.errors.append(f"{row['doc_id']}: no text extracted (scanned PDF? OCR is out of scope)")
            for c in chunks:
                out.write(json.dumps(c, ensure_ascii=False) + "\n")
            report.documents += 1
            report.chunks += len(chunks)
            report.words += sum(c["word_count"] for c in chunks)
            report.per_doc.append((row["title"], len(doc.pages), len(chunks), row["effective_date"]))
            if not row["effective_date"]:
                report.undated.append(row["title"])
    return report


def resolve_date(row: dict, overrides: dict) -> dict:
    """effective_date + where it came from: manifest hand edit > document_dates.yaml > text of the PDF."""
    if row.get("effective_date"):
        return {"effective_date": row["effective_date"], "date_source": "entered by hand in manifest.csv"}
    if row["title"] in overrides:
        o = overrides[row["title"]]
        return {"effective_date": str(o["date"]), "date_source": o.get("evidence", "document_dates.yaml")}
    d, evidence = document_date(PROJECT_ROOT / row["file_path"])
    return {"effective_date": d, "date_source": evidence}
