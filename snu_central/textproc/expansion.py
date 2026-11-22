"""Query expansion using synonyms.yaml (FR-4.6)."""

import re
from functools import lru_cache
from pathlib import Path

import yaml

from .analyzer import analyze


@lru_cache(maxsize=None)
def _load(path: str) -> list[list[str]]:
    with open(path, encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("groups", [])


def expand(query: str, synonyms_path: str | Path) -> list[str]:
    """Analyze `query`, then add terms of every synonym group that has a member phrase in the query."""
    terms = analyze(query)
    padded = " " + " ".join(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", query.lower())) + " "
    for group in _load(str(synonyms_path)):
        if any(f" {m.lower()} " in padded for m in group):
            for other in group:
                terms.extend(analyze(other))
    return list(dict.fromkeys(terms))   # dedupe, keep order


def synonym_words(synonyms_path: str | Path) -> list[str]:
    """Every single word in the synonym dictionary (they count as known words for spelling)."""
    return [w for group in _load(str(synonyms_path)) for phrase in group for w in re.findall(r"[a-z0-9]+", phrase.lower())]
