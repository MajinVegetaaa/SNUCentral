"""Spelling correction: "Did you mean ...?" (FR-4.11).

Isolated-term correction as in Manning, Raghavan & Schuetze, ch. 3:
  1. A query word is *known* if the documents contain it, contain its stem, or the SNU synonym
     dictionary lists it. Numbers and very short words are never corrected.
     Words seen even once count as known: checking the vocabulary showed that most once-seen
     words are real ("eighth", "viable"), and correcting them would do more harm than good.
  2. Candidates for an unknown word come from a character-bigram (k-gram) index over the
     vocabulary (words whose bigram sets overlap with Jaccard >= JACCARD_MIN), plus every
     vocabulary word exactly one edit away, which catches swapped letters ("refnud") that
     break bigram overlap.
  3. Candidates are ranked by Damerau-Levenshtein distance (adjacent transpositions cost 1), then
     same first letter, then frequency in the documents. Only distance <= 1 (words up to 5 letters)
     or <= 2 (longer words) is accepted; otherwise the word is left alone.
  4. If a query contains an unknown word with no close match ("pizza"), it is off-topic vocabulary,
     not a typo, and nothing is suggested.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from .analyzer import STOP_WORDS, analyze, tokenize

JACCARD_MIN = 0.3
MIN_LEN = 4                  # "ug", "pg", "cse": too short to correct safely
MIN_FREQ = 2                 # never suggest a word seen only once (it may itself be a typo in a PDF)
_ALPHABET = "abcdefghijklmnopqrstuvwxyz"


def edit_distance(a: str, b: str) -> int:
    """Damerau-Levenshtein distance (optimal string alignment): insert, delete, substitute, swap neighbours."""
    prev2: list[int] = []
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        prev2, prev = prev, cur
    return prev[-1]


def edits1(word: str) -> set[str]:
    """All strings one delete, swap, substitution or insertion away (Norvig)."""
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    return ({a + b[1:] for a, b in splits if b}
            | {a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1}
            | {a + c + b[1:] for a, b in splits if b for c in _ALPHABET}
            | {a + c + b for a, b in splits for c in _ALPHABET})


def bigrams(word: str) -> set[str]:
    w = f"${word}$"                                   # boundary marks make first/last letters count
    return {w[i:i + 2] for i in range(len(w) - 1)}


@dataclass
class Suggestion:
    text: str                                         # the corrected query
    changes: list[tuple[str, str]]                    # (original word, replacement)


class SpellChecker:
    def __init__(self, word_freq: dict[str, int], postings: dict, extra_known=()):
        self.freq = word_freq
        self.postings = postings                      # stem -> {chunk_id: tf}: gives each stem's df
        self.known_extra = {w.lower() for w in extra_known}
        self.kgram: dict[str, list[str]] = defaultdict(list)
        for w, f in word_freq.items():
            if f >= MIN_FREQ and w.isalpha() and len(w) >= 3:
                for g in bigrams(w):
                    self.kgram[g].append(w)

    def _seen(self, word: str) -> int:
        """How established a word is: max(surface count, document frequency of its stems)."""
        stems = analyze(word)
        df = min((len(self.postings.get(t, ())) for t in stems), default=0)
        return max(self.freq.get(word, 0), df)

    def known(self, word: str) -> bool:
        return word in self.known_extra or word in STOP_WORDS or self._seen(word) > 0

    def correct(self, word: str) -> str | None:
        """Best replacement for a word that occurs nowhere in the documents, or None."""
        if len(word) < MIN_LEN or not word.isalpha() or self.known(word):
            return None
        max_dist = 1 if len(word) <= 5 else 2
        grams = bigrams(word)
        overlap = Counter(w for g in grams for w in self.kgram.get(g, ()))
        cands = {w for w, shared in overlap.items()
                 if shared / (len(grams) + len(bigrams(w)) - shared) >= JACCARD_MIN}
        cands |= {w for w in edits1(word) if self.freq.get(w, 0) >= MIN_FREQ}
        best = None
        for cand in cands:
            if self.freq.get(cand, 0) < MIN_FREQ or abs(len(cand) - len(word)) > max_dist:
                continue
            d = edit_distance(word, cand)
            if d <= max_dist:
                key = (d, cand[0] != word[0], -self.freq[cand], cand)
                if best is None or key < best:
                    best = key
        return best[-1] if best else None

    def suggest(self, query: str) -> Suggestion | None:
        """Corrected query, or None. No suggestion when some unknown word has no close match at all:
        then the query uses vocabulary the documents do not have ("pizza margherita"), it is not a typo."""
        changes = []
        for tok in dict.fromkeys(tokenize(query)):
            if len(tok) < MIN_LEN or not tok.isalpha() or self.known(tok):
                continue
            fix = self.correct(tok)
            if fix is None:
                return None                             # unknown word with no near neighbour: off-topic
            changes.append((tok, fix))
        if not changes:
            return None
        text = query
        for old, new in changes:
            text = re.sub(rf"\b{re.escape(old)}\b", new, text, flags=re.I)
        return Suggestion(text, changes)
