"""processed_data/manifest.csv: one row per document (FR-1.3).

Columns filled by fetch.py are overwritten on every run. The MANUAL_FIELDS
are only auto-filled when empty, so hand edits (dates, department,
superseded flag) survive re-fetching.
"""

import csv
from pathlib import Path

FIELDS = [
    "doc_id", "source_id", "title", "category", "department", "folder",
    "source_url", "file_path", "sha256", "size_bytes",
    "fetched_at", "changed_at", "effective_date", "is_superseded",
    "duplicate_of", "status", "error",
]
MANUAL_FIELDS = ("department", "effective_date", "is_superseded")

# status values
NEW, CHANGED, UNCHANGED, FAILED, REMOVED = "new", "changed", "unchanged", "failed", "removed"


def read_manifest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["doc_id"]: {k: row.get(k, "") for k in FIELDS} for row in csv.DictReader(f)}


def write_manifest(path: Path, rows: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows.values(), key=lambda r: (r["source_id"], r["folder"], r["title"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in ordered:
            writer.writerow({k: row.get(k, "") for k in FIELDS})


def active_documents(rows: dict[str, dict], project_root: Path) -> list[dict]:
    """Rows that should be indexed: file present, not removed, not a duplicate."""
    return [
        r for r in rows.values()
        if r["status"] != REMOVED
        and not r["duplicate_of"]
        and r["file_path"]
        and (project_root / r["file_path"]).exists()
    ]
