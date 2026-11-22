"""Validate [n] markers against sent passages and resolve them to metadata (FR-6.5)."""

import re
from dataclasses import dataclass

_MARKER = re.compile(r"\[(\d+)\]")
_FANCY = re.compile(r"【\s*(\d+)[^】]*】|[\[［]\s*(\d+)\s*[\]］]")


def normalize(text: str) -> str:
    """Models sometimes emit 【3】 or [ 3 ]; turn them into plain [3] before validating."""
    return _FANCY.sub(lambda m: f"[{m.group(1) or m.group(2)}]", text)


@dataclass
class CitationCheck:
    valid: list[int]          # distinct passage numbers cited, in order of first use
    invalid: list[int]        # markers that point at no sent passage
    uncited_sentences: int    # sentences with no marker (not established by the documents, FR-6.5)

    @property
    def ok(self) -> bool:
        return not self.invalid and bool(self.valid)


def check(answer: str, n_passages: int) -> CitationCheck:
    answer = normalize(answer)
    nums = [int(m) for m in _MARKER.findall(answer)]
    valid = list(dict.fromkeys(n for n in nums if 1 <= n <= n_passages))
    invalid = list(dict.fromkeys(n for n in nums if not 1 <= n <= n_passages))
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n+", answer) if len(s.split()) >= 5]
    uncited = sum(1 for s in sentences if not _MARKER.search(s))
    return CitationCheck(valid, invalid, uncited)


def resolve(answer: str, results: list[tuple[dict, float]]) -> str:
    """Replace valid [n] with a short citation built from metadata; drop invalid markers."""
    def sub(m: re.Match) -> str:
        n = int(m.group(1))
        if not 1 <= n <= len(results):
            return ""
        c = results[n - 1][0]
        return f"[{n}: {c['document_name']}, p.{c['page_number']}]"
    return _MARKER.sub(sub, normalize(answer))


def strip_invalid(text: str, n_passages: int) -> str:
    """Remove markers that point at no sent passage (they are flagged separately in the UI)."""
    text = normalize(text)
    return _MARKER.sub(lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_passages else "", text)
