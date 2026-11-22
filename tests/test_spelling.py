"""Spelling correction (FR-4.11): edit distance vs hand-computed values, k-gram candidates, suggestions."""

from snu_central.generation import answer_question
from snu_central.generation.providers import LLMProvider
from snu_central.index.inverted_index import InvertedIndex
from snu_central.retrieval.bm25 import BM25Retriever
from snu_central.textproc.spelling import SpellChecker, bigrams, edit_distance, edits1


def test_edit_distance_hand_computed():
    assert edit_distance("kitten", "sitting") == 3        # k->s, e->i, +g
    assert edit_distance("refnud", "refund") == 1         # one adjacent swap (Damerau)
    assert edit_distance("hostle", "hostel") == 1
    assert edit_distance("hostle", "host") == 2
    assert edit_distance("", "abc") == 3 and edit_distance("same", "same") == 0


def test_bigrams_and_edits1():
    assert bigrams("cat") == {"$c", "ca", "at", "t$"}
    e = edits1("ab")
    assert {"b", "ba", "xb", "abx"} <= e and "ab" in e    # delete, swap, substitute, insert


def _speller():
    freq = {"refund": 40, "hostel": 30, "host": 50, "list": 12, "sit": 20, "attendance": 60,
            "chnage": 1, "change": 25, "policy": 80}
    postings = {"refund": {"a": 1, "b": 1}, "hostel": {"a": 1, "c": 1}, "attend": {"a": 1, "b": 1},
                "chnage": {"z": 1}, "chang": {"a": 1, "b": 1}, "polici": {"a": 1, "b": 1}}
    return SpellChecker(freq, postings, extra_known=["cgpa"])


def test_corrections_prefer_smallest_distance_then_first_letter():
    sp = _speller()
    assert sp.correct("refnud") == "refund"
    assert sp.correct("hostle") == "hostel"              # distance 1 beats the more frequent "host" (2)
    assert sp.correct("lsit") == "list"                  # tie at distance 1: same first letter wins over "sit"
    assert sp.correct("chnage") is None                  # it occurs once in the documents: treated as a real word


def test_known_words_are_left_alone():
    sp = _speller()
    assert sp.correct("refund") is None and sp.correct("cgpa") is None and sp.correct("2025") is None
    assert sp.suggest("refund policy") is None


def test_off_topic_words_get_no_suggestion():
    sp = _speller()
    assert sp.suggest("refnud policy").text == "refnud policy".replace("refnud", "refund")
    assert sp.suggest("pizza refnud") is None             # "pizza" has no near neighbour: not a typo


class _Echo(LLMProvider):
    model_used = "fake"

    def stream(self, messages):
        yield "Refunds follow the policy [1]."


def test_query_with_only_misspelled_words_is_searched_corrected():
    chunks = [{"chunk_id": "a", "doc_id": "d", "text": "refund policy for withdrawal refund", "document_name": "Fee",
               "section": "5", "page_number": 15, "department": "Finance", "file_path": "x.pdf"},
              {"chunk_id": "b", "doc_id": "d", "text": "hostel curfew rules apply", "document_name": "HB",
               "section": "9", "page_number": 3, "department": "SA", "file_path": "y.pdf"}]
    ret = BM25Retriever(InvertedIndex.build(chunks), chunks)
    cfg = {"retrieval": {"top_k": 5, "abstain_threshold": 0.05}, "llm": {"prompt_version": "v4"},
           "paths": {"query_log": "logs/test_queries.jsonl"}}
    a = answer_question("refnud", ret, cfg, provider=_Echo())
    assert a.corrected_from == "refnud" and a.query == "refund" and a.status == "answered"


def test_correction_can_be_turned_off():
    chunks = [{"chunk_id": "a", "doc_id": "d", "text": "refund policy refund", "document_name": "Fee",
               "section": "5", "page_number": 15, "department": "Finance", "file_path": "x.pdf"}]
    ret = BM25Retriever(InvertedIndex.build(chunks), chunks)
    cfg = {"retrieval": {"top_k": 5, "abstain_threshold": 0.05}, "llm": {"prompt_version": "v4"},
           "paths": {"query_log": "logs/test_queries.jsonl"}}
    a = answer_question("refnud", ret, cfg, provider=_Echo(), correct_spelling=False)
    assert a.corrected_from is None and a.status == "abstained"
