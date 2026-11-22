"""Ranking of chunks for a query (FR-4.x)."""

from ..config import load_config, project_path
from ..index import read_chunks
from ..index.store import load_index
from .bm25 import BM25Retriever
from .tfidf import TfidfCosineRetriever


def load_retriever(cfg: dict | None = None, ranker: str | None = None):
    """Build the retriever named in config.yaml (or `ranker`) from the saved index."""
    cfg = cfg or load_config()
    r = cfg["retrieval"]
    index = load_index(project_path(cfg, "index"))
    chunks = read_chunks(project_path(cfg, "chunks"))
    syn = project_path(cfg, "synonyms")
    if (ranker or r["ranker"]) == "tfidf":
        return TfidfCosineRetriever(index, chunks, syn)
    return BM25Retriever(index, chunks, syn, r["bm25_k1"], r["bm25_b"])
