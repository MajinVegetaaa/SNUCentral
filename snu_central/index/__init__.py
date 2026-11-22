"""Inverted index construction and persistence (FR-3.x)."""

import json
import re
from pathlib import Path


def read_chunks(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def dedupe_chunks(chunks: list[dict]) -> list[dict]:
    """Drop chunks whose text is identical to an earlier one (the Fee Policy repeats whole passages per programme).

    The first copy is kept and records the others in `duplicate_ids`, so no provenance is lost and
    old chunk ids can still be resolved. Without this, repeated text inflates document frequency
    and fills the top-K with copies of one passage.
    """
    kept: dict[str, dict] = {}
    for c in chunks:
        key = _norm(c["text"])
        if key in kept:
            kept[key].setdefault("duplicate_ids", []).append(c["chunk_id"])
        else:
            kept[key] = dict(c)
    return list(kept.values())


def write_chunks(chunks: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
