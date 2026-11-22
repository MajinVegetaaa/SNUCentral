"""Tokenize, stop words, Porter stemming, keep numbers. ONE analyzer for docs and queries (FR-2.5, FR-4.2).

Nothing else in the project tokenizes or stems. The index stores `ANALYZER_HASH`
so a change here forces a rebuild (NFR-6.3).
"""

import hashlib
import re

from nltk.stem.porter import PorterStemmer

# Small hand-picked list. Negations and modals (no, not, may, must, shall) are KEPT: they decide what a policy means.
STOP_WORDS = frozenset("""
a an and are as at be been being by for from has have had he her his i if in into is it its of on or
our she so than that the their them then there these they this those to was we were what when where
which who whom why will with you your do does did can about also any all each such
how after me my should would could
""".split())

# Keeps dotted/hyphenated/slashed terms together ("re-evaluation", "3.5", "10/15") but splits other punctuation.
_TOKEN = re.compile(r"[a-z0-9]+(?:[-./][a-z0-9]+)*")
_stemmer = PorterStemmer()
_stem_cache: dict[str, str] = {}


def _stem(word: str) -> str:
    s = _stem_cache.get(word)
    if s is None:
        s = _stem_cache[word] = word if word.isdigit() or not word.isalpha() else _stemmer.stem(word)
    return s


def tokenize(text: str) -> list[str]:
    """Lowercase and split into raw tokens (no stop-word removal, no stemming)."""
    return _TOKEN.findall(text.lower().replace("’", "'").replace("'s ", " "))


def analyze(text: str) -> list[str]:
    """Text -> list of index terms. Used for chunks at build time and for queries at search time."""
    terms = []
    for tok in tokenize(text):
        if tok in STOP_WORDS:
            continue
        # "re-evaluation" -> also its parts, so "evaluation" and "re-evaluation" can meet.
        parts = [tok] + re.split(r"[-/]", tok) if re.search(r"[-/]", tok) else [tok]
        terms.extend(_stem(p) for p in dict.fromkeys(parts) if p and p not in STOP_WORDS)
    return terms


ANALYZER_HASH = hashlib.sha1(
    (repr(sorted(STOP_WORDS)) + _TOKEN.pattern + "porter-nltk-v1").encode()
).hexdigest()[:12]
