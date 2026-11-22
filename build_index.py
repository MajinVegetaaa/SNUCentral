"""Extract, clean and chunk all active documents, then build the index.

Usage:
    python build_index.py

Step 1: manifest -> processed_data/chunks.jsonl
Step 2: drop exact-duplicate chunks, then chunks.jsonl -> indexes/index.pkl
"""

from snu_central.config import load_config, project_path
from snu_central.index import dedupe_chunks, read_chunks, write_chunks
from snu_central.index.inverted_index import InvertedIndex
from snu_central.index.store import save_index
from snu_central.ingest import run_ingest


def main() -> None:
    cfg = load_config()
    report = run_ingest(cfg)

    print(f"{'pages':>6} {'chunks':>6}  {'date':10}  document")
    for title, pages, chunks, dated in sorted(report.per_doc, key=lambda x: -x[2]):
        print(f"{pages:>6} {chunks:>6}  {dated or '-':10}  {title[:70]}")
    avg = report.words / report.chunks if report.chunks else 0
    print(f"\n{report.documents} documents -> {report.chunks} chunks, "
          f"{report.words} words (avg {avg:.0f} words/chunk)")
    print(f"Chunks: {project_path(cfg, 'chunks')}")
    if report.undated:
        print(f"No date stated in {len(report.undated)} document(s): {'; '.join(report.undated)}")
    if report.errors:
        print(f"\nErrors: {len(report.errors)}")
        for e in report.errors:
            print(f"  {e}")

    chunks_path = project_path(cfg, "chunks")
    raw = read_chunks(chunks_path)
    chunks = dedupe_chunks(raw)
    write_chunks(chunks, chunks_path)
    print(f"Deduplicated: {len(raw)} -> {len(chunks)} chunks ({len(raw) - len(chunks)} exact repeats merged)")
    idx = InvertedIndex.build(chunks)
    save_index(idx, project_path(cfg, "index"))
    print(f"Index: {len(idx.postings)} terms, {idx.n_docs} chunks, avg length {idx.avg_len:.1f} "
          f"-> {project_path(cfg, 'index')}")


if __name__ == "__main__":
    main()
