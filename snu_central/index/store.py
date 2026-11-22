"""Save/load indexes/index.pkl with analyzer_hash check (NFR-6.3)."""

import pickle
import time
from pathlib import Path

from ..textproc.analyzer import ANALYZER_HASH
from .inverted_index import InvertedIndex

INDEX_FORMAT = 2          # 2: adds the surface-word vocabulary used for spelling suggestions


def save_index(idx: InvertedIndex, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump({"index": idx, "analyzer_hash": ANALYZER_HASH, "format": INDEX_FORMAT,
                     "built_at": time.time()}, f)


def load_index(path: Path) -> InvertedIndex:
    """Load an index we built ourselves (pickle is unsafe for untrusted files)."""
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run: python build_index.py")
    with open(path, "rb") as f:
        data = pickle.load(f)
    if data["analyzer_hash"] != ANALYZER_HASH or data.get("format") != INDEX_FORMAT:
        raise RuntimeError("Index was built with a different analyzer or format. Rebuild: python build_index.py")
    return data["index"]
