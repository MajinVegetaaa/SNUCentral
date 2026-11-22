"""Generation layer without any network: citations, prompt, gate abstention, fallback."""

from snu_central.generation import answer_question
from snu_central.generation.citations import check, resolve
from snu_central.generation.prompt import build_messages
from snu_central.generation.providers import LLMProvider, LLMUnavailable
from snu_central.index.inverted_index import InvertedIndex
from snu_central.retrieval.bm25 import BM25Retriever

CHUNKS = [{"chunk_id": "a", "doc_id": "d1", "text": "attendance minimum seventy five percent", "document_name": "Attendance Policy",
           "section": "4.2", "page_number": 7, "department": "Office of Academic Affairs"},
          {"chunk_id": "b", "doc_id": "d2", "text": "hostel curfew rules", "document_name": "Handbook", "section": "9",
           "page_number": 3, "department": "Student Affairs"}]
CFG = {"retrieval": {"top_k": 5, "abstain_threshold": 0.05}, "llm": {"prompt_version": "v1"},
       "paths": {"query_log": "logs/test_queries.jsonl"}}


class Fake(LLMProvider):
    def __init__(self, text): self.text, self.model_used = text, "fake"
    def stream(self, messages): yield from self.text.split(" ", 1)[:1] + [" " + self.text.split(" ", 1)[1]]


class Down(LLMProvider):
    def stream(self, messages): raise LLMUnavailable("429")


def retriever():
    return BM25Retriever(InvertedIndex.build(CHUNKS), CHUNKS)


def test_citation_check_flags_invalid_and_uncited():
    c = check("Students need 75 percent attendance [1]. This sentence has no marker at all. See [7].", 2)
    assert c.valid == [1] and c.invalid == [7] and c.uncited_sentences == 1 and not c.ok


def test_resolve_replaces_valid_drops_invalid():
    res = [(CHUNKS[0], 1.0)]
    assert resolve("Yes [1][9].", res) == "Yes [1: Attendance Policy, p.7]."


def test_prompt_numbers_passages_and_has_rules():
    m = build_messages("q?", [(CHUNKS[0], 1.0), (CHUNKS[1], 0.5)])
    assert '<passage id="1"' in m[1]["content"] and '<passage id="2"' in m[1]["content"]
    assert "ONLY from the passages" in m[0]["content"]


def test_gate_abstains_without_calling_llm():
    a = answer_question("pizza recipe", retriever(), CFG, provider=Down())   # Down would raise if called
    assert a.status == "abstained" and "isn't covered" in a.text


def test_answered_path_validates_citations():
    a = answer_question("attendance", retriever(), CFG, provider=Fake("Seventy five percent is needed [1]."))
    assert a.status == "answered" and a.citation.ok


def test_llm_failure_falls_back_to_passages():
    a = answer_question("attendance", retriever(), CFG, provider=Down())
    assert a.status == "fallback" and a.results


def test_fullwidth_brackets_are_normalised():
    assert check("Need 75 percent attendance to sit exams 【1】【2】.", 2).valid == [1, 2]


def test_discovery_skips_audio_and_guard_models():
    from snu_central.generation.providers import OpenAICompatProvider
    p = OpenAICompatProvider.__new__(OpenAICompatProvider)
    live = ["meta-llama/llama-prompt-guard-2-86m", "whisper-large-v3", "canopylabs/orpheus-v1-english",
            "openai/gpt-oss-safeguard-20b", "allam-2-7b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
    assert p.discover(live) == ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "allam-2-7b"]


def test_expand_context_adds_neighbours_marked_as_context():
    from snu_central.generation import expand_context
    cs = [{"chunk_id": f"c{i}", "doc_id": "d", "text": f"t{i}", "section": "S", "page_number": 1} for i in range(5)]
    r = type("R", (), {"chunks": {c["chunk_id"]: c for c in cs}})()
    out = expand_context([(cs[2], 3.0)], r, n_top=1, cap=8)
    assert [c["chunk_id"] for c, _ in out] == ["c2", "c3", "c1"] and out[1][0]["_context"] and "_context" not in cs[3]


def test_marker_with_dagger_suffix_is_normalised():
    assert check("Seats are posted online 【3†a.i】.", 5).valid == [3]


def test_fullwidth_marker_with_line_ref_is_normalised():
    assert check("Refund is 75% 【1†L4-L5】 and 50% 【3†L1-L2】 [ 2 ].", 5).valid == [1, 3, 2]


def test_expand_context_skips_other_sections_on_other_pages():
    from snu_central.generation import expand_context
    cs = [{"chunk_id": "a", "doc_id": "d", "text": "x", "section": "Doctoral fees", "page_number": 9},
          {"chunk_id": "b", "doc_id": "d", "text": "y", "section": "MBA refund", "page_number": 10},
          {"chunk_id": "c", "doc_id": "d", "text": "z", "section": "Table 4.1", "page_number": 10}]
    r = type("R", (), {"chunks": {c["chunk_id"]: c for c in cs}})()
    out = [c["chunk_id"] for c, _ in expand_context([(cs[1], 2.0)], r, n_top=1, cap=8)]
    assert out == ["b", "c"]          # same-page table kept, other-page other-section chunk dropped


def test_log_redaction_removes_personal_data():
    from snu_central.generation import redact
    q = "I am ab123@snu.edu.in, roll 2110110456, phone +91 98765 43210: attendance rule?"
    assert redact(q) == "I am <email>, roll <id>, phone <number>: attendance rule?"


def test_prompt_versions_build_on_each_other():
    from snu_central.generation.prompt import PROMPTS
    assert "answer only part of the question" in PROMPTS["v3"] and "10. Be concise" in PROMPTS["v3"]
    assert "Never add examples" in PROMPTS["v4"] and "answer only part of the question" in PROMPTS["v4"]


def test_statement_splitting_for_groundedness():
    import sys
    sys.path.insert(0, ".")
    from evaluate_answers import split_statements
    ans = ("**Penalties**\n- Marks reduction\n- Grade reduction\n- An F grade in the course [2][5].\n\n"
           "The documents do not specify penalties for repeat offences.\nSo the rule applies to everyone.")
    got = [(t, m, how) for t, m, how in split_statements(ans)]
    assert ("Penalties", [], "none") not in got                         # heading skipped
    assert got[0] == ("Marks reduction", [2, 5], "list")                # inherits the list's citation
    assert got[2][2] == "own" and got[3][2] == "absence" and got[4][2] == "none"


def test_declined_answers_are_recognised():
    from snu_central.generation import is_declined
    assert is_declined("I could not find this in the documents I have. You may contact the Food Committee.")
    assert is_declined("I’m sorry, but I can’t help with that.")
    assert not is_declined("Undergraduate students may work up to 20 hours per week [3].")


def test_backup_key_used_only_after_401(monkeypatch):
    import httpx2
    from openai import AuthenticationError
    from snu_central.generation.providers import OpenAICompatProvider
    monkeypatch.setenv("TEST_KEY_A", "bad-key")
    monkeypatch.setenv("TEST_KEY_B", "good-key")
    cfg = {"api_key_env": "TEST_KEY_A", "backup_key_envs": ["TEST_KEY_B", "TEST_KEY_MISSING"],
           "base_url": "http://localhost:9", "timeout_seconds": 1, "model": "m", "temperature": 0}

    class P(OpenAICompatProvider):
        def available_models(self):
            return ["m"]

        def _request(self, model, messages):
            if self.key_name == "TEST_KEY_A":
                resp = httpx2.Response(401, request=httpx2.Request("POST", "http://localhost:9"))
                raise AuthenticationError("invalid key", response=resp, body=None)
            return iter([type("C", (), {"choices": [type("Ch", (), {"delta": type("D", (), {"content": "ok [1]"})()})()]})()])

    p = P(cfg)
    assert "".join(p.stream([])) == "ok [1]"
    assert p.key_name == "TEST_KEY_B" and "TEST_KEY_A was rejected" in p.notice
    assert "bad-key" not in p.notice and "good-key" not in p.notice          # never reveal key values


def test_no_backup_left_gives_clear_error(monkeypatch):
    import httpx2
    import pytest
    from openai import AuthenticationError
    from snu_central.generation.providers import LLMUnavailable, OpenAICompatProvider
    monkeypatch.setenv("TEST_KEY_A", "bad-key")
    cfg = {"api_key_env": "TEST_KEY_A", "base_url": "http://localhost:9", "timeout_seconds": 1,
           "model": "m", "temperature": 0}

    class P(OpenAICompatProvider):
        def available_models(self):
            return ["m"]

        def _request(self, model, messages):
            resp = httpx2.Response(401, request=httpx2.Request("POST", "http://localhost:9"))
            raise AuthenticationError("invalid key", response=resp, body=None)

    with pytest.raises(LLMUnavailable, match="TEST_KEY_A was rejected"):
        list(P(cfg).stream([]))
