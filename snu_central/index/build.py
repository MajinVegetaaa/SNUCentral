"""Build everything from the manifest: PDFs -> chunks.jsonl -> de-duplicated -> indexes/index.pkl.

Shared by build_index.py (command line) and app.py (first start on a fresh deployment).
"""

from dataclasses import dataclass

from ..config import project_path
from ..ingest import IngestReport, run_ingest
from . import dedupe_chunks, read_chunks, write_chunks
from .inverted_index import InvertedIndex
from .store import load_index, save_index


@dataclass
class BuildResult:
    report: IngestReport
    raw_chunks: int
    chunks: int
    index: InvertedIndex


def build_all(cfg: dict) -> BuildResult:
    report = run_ingest(cfg)
    path = project_path(cfg, "chunks")
    raw = read_chunks(path)
    chunks = dedupe_chunks(raw)
    write_chunks(chunks, path)
    idx = InvertedIndex.build(chunks)
    save_index(idx, project_path(cfg, "index"))
    return BuildResult(report, len(raw), len(chunks), idx)


def ensure_index(cfg: dict) -> bool:
    """Build the index if it is missing or was built by a different analyzer/format. True if it was (re)built."""
    try:
        load_index(project_path(cfg, "index"))
        if project_path(cfg, "chunks").exists():
            return False
    except (FileNotFoundError, RuntimeError):
        pass
    build_all(cfg)
    return True
