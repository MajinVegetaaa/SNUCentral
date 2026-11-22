"""Analyzer: tokenization, stop words, stemming, numbers preserved."""

from snu_central.index.inverted_index import InvertedIndex
from snu_central.textproc.analyzer import analyze


def test_stop_words_and_stemming():
    assert analyze("The students are withdrawing from courses") == ["student", "withdraw", "cours"]


def test_negation_kept():
    assert "not" in analyze("attendance is not optional")


def test_numbers_and_dates_kept():
    terms = analyze("minimum 75% attendance, CGPA of 3.5 by 15/10/2025")
    assert {"75", "3.5", "15/10/2025", "cgpa"} <= set(terms)


def test_hyphenated_term_keeps_parts():
    terms = analyze("re-evaluation")
    assert "re-evaluation" in terms and "evalu" in terms


def test_query_and_document_use_same_analyzer():
    assert analyze("Withdrawal") == analyze("withdrawal")


def test_inverted_index_construction():
    chunks = [
        {"chunk_id": "a", "text": "hostel fee refund refund"},
        {"chunk_id": "b", "text": "hostel curfew rules"},
        {"chunk_id": "c", "text": "exam rules"},
    ]
    idx = InvertedIndex.build(chunks)
    assert idx.postings["refund"] == {"a": 2}
    assert idx.df("hostel") == 2 and idx.df("missing") == 0
    assert idx.n_docs == 3 and idx.lengths["a"] == 4
    assert idx.avg_len == 3.0   # (4 + 3 + 2) / 3
    assert abs(idx.idf["hostel"] - 0.17609125905568124) < 1e-9   # log10(3/2)


def test_dedupe_chunks_merges_exact_repeats_and_keeps_provenance():
    from snu_central.index import dedupe_chunks
    cs = [{"chunk_id": "a", "text": "Fee is  5,000 per credit."},
          {"chunk_id": "b", "text": "fee is 5,000 per credit"},
          {"chunk_id": "c", "text": "Something else"}]
    out = dedupe_chunks(cs)
    assert [c["chunk_id"] for c in out] == ["a", "c"] and out[0]["duplicate_ids"] == ["b"]



def test_numbered_notes_are_not_headings():
    from snu_central.ingest.chunk import _reads_as_sentence
    assert _reads_as_sentence("2. Tuition Fee Waiver not applicable for Sponsored Candidates")
    assert _reads_as_sentence("1. Tuition Fee Waiver is for 2 semesters only")
    assert not _reads_as_sentence("4.3 Disciplinary Committee")
    assert not _reads_as_sentence("Notes are useful")          # not numbered: other rules decide



def test_document_date_rules():
    from snu_central.ingest.dates import date_from_text, find_dates
    assert [d.isoformat() for d in find_dates("29.9.23, June 23, 2025 and 5 Feb, 2026")] == \
        ["2023-09-29", "2025-06-23", "2026-02-05"]
    release = ("Release Control Release Date Version No: 10.05.2015 1.0 First 28.07.2020 1.8 Fees updated "
               "POLICY RATIFIED BY: Registrar 01.01.2030")
    assert date_from_text(["cover", release])[0] == "2020-07-28"          # latest release, not the ratification
    assert date_from_text(["Effective Date: February 2013 To remain"])[0] == "2013-02"
    assert date_from_text(["The composition is effective from 04 December 2023."])[0] == "2023-12-04"
    assert date_from_text(["APPROVED BY THE OFFICE OF THE DEAN IN JULY 2024"])[0] == "2024-07"
    assert date_from_text(["Holiday List 2026: January 1, 2026 New Year"]) == ("", "")   # never guess


def test_staleness_warning_handles_month_precision():
    from snu_central.ui.components import date_warning
    assert "Last revised 2013-02" in date_warning({"effective_date": "2013-02"}, 3)
    assert date_warning({"effective_date": "2099-01-01"}, 3) is None
    assert date_warning({"effective_date": ""}, 3) is None
