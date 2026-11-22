"""Fetch all sources, store changed files, update the manifest (FR-1.7).

Re-running is safe: unchanged files are not rewritten, a failed download
keeps the previous copy, and documents that disappeared from a source are
marked `removed` (their file is kept until you delete it).
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..config import PROJECT_ROOT, project_path
from . import manifest as mf
from .direct import fetch_direct
from .downloader import Downloader, sha256
from .models import FetchedDoc, SourceResult
from .snulinks import fetch_snulinks

FETCHERS = {
    "pdf": fetch_direct,
    "snulinks_embedded_pdf": fetch_snulinks,
}


@dataclass
class FetchReport:
    by_status: dict[str, list[str]] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)

    def add(self, status: str, label: str) -> None:
        self.by_status.setdefault(status, []).append(label)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _category(src: dict, doc: FetchedDoc, valid: dict) -> str:
    """Per-document override, else first matching rule on "<folder> > <title>", else source default."""
    category = doc.category
    if not category:
        haystack = f"{doc.folder} > {doc.title}"
        category = next((r["category"] for r in src.get("category_rules", [])
                         if re.search(r["match"], haystack, re.I)), src["category"])
    if category not in valid:
        raise ValueError(f"{doc.doc_id}: category {category!r} is not in config.yaml categories")
    return category


def _department(src: dict, doc: FetchedDoc) -> str:
    if doc.department:
        return doc.department
    if src.get("department"):
        return src["department"]
    haystack = f"{doc.folder} > {doc.title}"
    for rule in src.get("departments", []):
        if re.search(rule["match"], haystack, re.I):
            return rule["department"]
    return ""


def _superseded_hint(src: dict, doc: FetchedDoc) -> str:
    pattern = src.get("superseded_pattern")
    if pattern and re.search(pattern, f"{doc.folder} > {doc.title}", re.I):
        return "true"
    return ""


def _target_path(docs_root: Path, category: str, doc: FetchedDoc, rows: dict) -> Path:
    """static/documents/<category>/<filename>, avoiding clashes between documents."""
    path = docs_root / category / doc.filename
    taken = {r["file_path"] for r in rows.values() if r["doc_id"] != doc.doc_id}
    if str(path.relative_to(PROJECT_ROOT)) in taken:
        stem, ext = doc.filename.rsplit(".", 1)
        path = docs_root / category / f"{stem}__{doc.doc_id}.{ext}"
    return path


def _store(doc: FetchedDoc, src: dict, category: str, rows: dict, docs_root: Path, now: str,
           report: FetchReport) -> None:
    digest = sha256(doc.data)
    old = rows.get(doc.doc_id)
    path = _target_path(docs_root, category, doc, rows)
    rel = str(path.relative_to(PROJECT_ROOT))

    if old is None:
        status = mf.NEW
    elif old["sha256"] != digest or old["file_path"] != rel or not path.exists():
        status = mf.CHANGED
    else:
        status = mf.UNCHANGED

    if status != mf.UNCHANGED:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(doc.data)
        # A renamed document (e.g. new version filename) leaves its old file behind.
        if old and old["file_path"] and old["file_path"] != rel:
            old_path = (PROJECT_ROOT / old["file_path"]).resolve()
            if old_path.is_file() and docs_root.resolve() in old_path.parents:
                old_path.unlink()

    row = dict(old) if old else {k: "" for k in mf.FIELDS}
    row.update(
        doc_id=doc.doc_id,
        source_id=doc.source_id,
        title=doc.title,
        category=category,
        folder=doc.folder,
        source_url=doc.url,
        file_path=rel,
        sha256=digest,
        size_bytes=str(len(doc.data)),
        fetched_at=now,
        changed_at=now if status != mf.UNCHANGED else row.get("changed_at", now),
        status=status,
        error="",
        duplicate_of="",
    )
    if not row["department"]:
        row["department"] = _department(src, doc)
    if not row["is_superseded"]:
        row["is_superseded"] = _superseded_hint(src, doc)
    rows[doc.doc_id] = row
    report.add(status, f"{doc.doc_id}  {doc.title}")


def _mark_duplicates(rows: dict, source_order: list[str], report: FetchReport) -> None:
    """FR-1.5: identical files (same SHA-256) are indexed once; earliest source wins."""
    first_by_hash: dict[str, str] = {}
    live = [r for r in rows.values() if r["status"] != mf.REMOVED and r["sha256"]]
    rank = {sid: i for i, sid in enumerate(source_order)}
    for r in sorted(live, key=lambda r: (rank.get(r["source_id"], 99), r["doc_id"])):
        keeper = first_by_hash.setdefault(r["sha256"], r["doc_id"])
        r["duplicate_of"] = "" if keeper == r["doc_id"] else keeper
        if r["duplicate_of"]:
            report.duplicates.append(f"{r['doc_id']} = {keeper}  ({r['title']})")


def run_fetch(cfg: dict, sources: dict, only: list[str] | None = None) -> FetchReport:
    docs_root = project_path(cfg, "documents")
    manifest_path = project_path(cfg, "manifest")
    rows = mf.read_manifest(manifest_path)
    report = FetchReport()
    dl = Downloader()
    now = _now()

    for source_id, src in sources.items():
        if only and source_id not in only:
            continue
        fetcher = FETCHERS.get(src.get("type"))
        if fetcher is None:
            report.failures.append(f"{source_id}: unknown source type {src.get('type')!r}")
            continue

        print(f"Fetching {source_id} ({src['name']}) ...", flush=True)
        result: SourceResult = fetcher(source_id, src, dl)

        seen = set()
        for doc in result.docs:
            _store(doc, src, _category(src, doc, cfg["categories"]), rows, docs_root, now, report)
            seen.add(doc.doc_id)

        report.skipped.extend(f"{source_id}: {r}" for r in result.skipped)

        failed_ids = set()
        for f in result.failures:
            report.failures.append(f"{f.source_id}: {f.url}  ->  {f.error}")
            if f.doc_id:
                failed_ids.add(f.doc_id)
                if f.doc_id in rows:          # keep the previous copy, just flag it
                    rows[f.doc_id].update(status=mf.FAILED, error=f.error)

        # If the whole source failed (e.g. index page down), don't mark everything removed.
        source_down = not result.docs and result.failures and not any(f.doc_id for f in result.failures)
        if not source_down:
            for doc_id, row in rows.items():
                if row["source_id"] == source_id and doc_id not in seen and doc_id not in failed_ids \
                        and row["status"] != mf.REMOVED:
                    row["status"] = mf.REMOVED
                    report.add(mf.REMOVED, f"{doc_id}  {row['title']}")

    _mark_duplicates(rows, list(sources), report)
    mf.write_manifest(manifest_path, rows)
    return report
