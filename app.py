"""Entry point: Streamlit chat app. Usage: streamlit run app.py"""

import os

import streamlit as st

from snu_central.config import load_config
from snu_central.generation import Answer, answer_stream, is_declined
from snu_central.generation.citations import strip_invalid
from snu_central.generation.providers import LLMUnavailable, get_provider
from snu_central.index.build import ensure_index
from snu_central.retrieval import load_retriever
from snu_central.ui.components import EXAMPLES, department_note, render_sources

st.set_page_config(page_title="SNU Central", page_icon=":material/school:", layout="centered")

try:  # Streamlit secrets are an alternative to .env / environment (NFR-7.1)
    for name in ("GROQ_API_KEY", "GROQ_API_KEY_2"):
        if name in st.secrets:
            os.environ.setdefault(name, st.secrets[name])
except Exception:  # noqa: BLE001 - no secrets file is fine
    pass

CFG = load_config()


@st.cache_resource(show_spinner="Building the search index (first start only, about 10 seconds)…")
def index_ready() -> bool:
    """On a fresh deployment there is no index yet: build it once from the documents in static/documents/."""
    return ensure_index(CFG)


@st.cache_resource(show_spinner="Loading the index…")
def get_retriever(ranker: str):
    index_ready()
    return load_retriever(CFG, ranker)


@st.cache_resource
def get_cached_provider():
    return get_provider(CFG)      # raises LLMUnavailable (not cached) until a key exists


def provider_or_none():
    try:
        return get_cached_provider()
    except LLMUnavailable:
        return None


# ---- sidebar ---------------------------------------------------------------------------------
with st.sidebar:
    st.header("SNU Central")
    st.caption("Ask about Shiv Nadar University policies. Answers come only from the official documents indexed here, "
               "and every statement links back to its source.")
    ranker = st.segmented_control("Ranking method", ["bm25", "tfidf"], default=CFG["retrieval"]["ranker"],
                                  format_func=lambda x: {"bm25": "BM25", "tfidf": "TF-IDF"}[x]) or CFG["retrieval"]["ranker"]
    if st.button("Clear conversation", icon=":material/delete:"):
        st.session_state.messages = []
    st.caption("Not an official source. For decisions that affect you, confirm with the office named under each answer.")

try:
    retriever = get_retriever(ranker)
except (FileNotFoundError, RuntimeError) as e:
    st.error(f"{e}", icon=":material/error:")
    st.stop()

stale_years = CFG["app"]["stale_after_years"]
pdf_base = CFG["app"].get("pdf_base_url", "")
st.session_state.setdefault("messages", [])


def render_spelling(ans: Answer, key) -> None:
    """FR-4.11: say that a spelling-corrected query was searched and offer the original wording."""
    if ans.corrected_from:
        st.caption(f'Showing results for "{ans.query}". Corrected from "{ans.corrected_from}".')
        st.button(f'Search for "{ans.corrected_from}" as typed', key=f"astyped_{key}", type="tertiary",
                  icon=":material/spellcheck:",
                  on_click=lambda q=ans.corrected_from: st.session_state.update(pending={"text": q, "spell": False}))


def render_assistant(msg: dict) -> None:
    ans: Answer = msg["answer"]
    terms = set(retriever.query_terms(ans.query))
    n = len(ans.results)
    render_spelling(ans, msg["id"])
    if msg["status"] == "answered" and is_declined(msg["text"]):     # the LLM said the documents don't cover it
        st.info(msg["text"], icon=":material/search_off:")
        if ans.notice:
            st.warning(ans.notice, icon=":material/info:")
        render_sources(ans.results, terms, [], stale_years, "Closest sections found (probably not relevant)",
                       expanded=False, pdf_base_url=pdf_base)
    elif msg["status"] == "answered":
        st.markdown(msg["text"])
        if ans.notice:
            st.warning(ans.notice, icon=":material/info:")
        if ans.citation.invalid:
            st.warning(f"Removed citation(s) {ans.citation.invalid} that do not match any retrieved passage.",
                       icon=":material/report:")
        if not ans.citation.valid:
            st.warning("This answer has no valid citation. Treat it as unverified and check the sources below.",
                       icon=":material/report:")
        elif ans.citation.uncited_sentences:
            st.caption(f"{ans.citation.uncited_sentences} sentence(s) carry no citation marker. "
                       "Statements without a source are not established by the documents.")
        note = department_note(ans.results, ans.citation.valid)
        if note:
            st.caption(note)
        render_sources(ans.results, terms, ans.citation.valid, stale_years, "Other retrieved sections", pdf_base_url=pdf_base)
    elif msg["status"] == "abstained":
        st.info(msg["text"], icon=":material/search_off:")
        if n:
            render_sources(ans.results, terms, [], stale_years, "Closest sections found (probably not relevant)",
                           expanded=False, pdf_base_url=pdf_base)
    else:  # fallback (FR-5.12)
        st.warning(msg["text"], icon=":material/cloud_off:")
        if ans.reason:
            st.caption(f"Reason: {ans.reason}")
        render_sources(ans.results, terms, [], stale_years, "Relevant sections", pdf_base_url=pdf_base)


# ---- chat ------------------------------------------------------------------------------------
st.title("SNU Central", anchor=False)

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        if m["role"] == "user":
            st.markdown(m["text"])
        else:
            render_assistant(m)

pending = st.session_state.pop("pending", None) or {}
typed = st.chat_input("Ask about SNU policies…", max_chars=CFG["app"]["max_input_chars"], submit_mode="disable")
prompt = typed or pending.get("text")
correct_spelling = bool(typed) or pending.get("spell", True)

if not st.session_state.messages and not prompt:
    st.caption("Ask a question in plain words. You do not need to know the document name. Try one of these:")
    with st.container():
        for q in EXAMPLES:
            st.button(q, key=f"ex_{q}", on_click=lambda q=q: st.session_state.update(pending={"text": q}),
                      icon=":material/arrow_forward:", width="stretch")


if prompt:
    prompt = prompt.strip()[: CFG["app"]["max_input_chars"]]
    st.session_state.messages.append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        slot = st.empty()
        shown, final = "", None
        with st.spinner("Searching the documents…"):
            stream = answer_stream(prompt, retriever, CFG, provider_or_none(), correct_spelling)
            for item in stream:
                if isinstance(item, Answer):
                    final = item
                else:
                    shown += item
                    slot.markdown(shown + " ▌")
        text = final.text
        if final.status == "answered":
            text = strip_invalid(final.text, len(final.results))
        slot.empty()
        msg = {"role": "assistant", "status": final.status, "text": text, "answer": final,
               "id": len(st.session_state.messages)}
        st.session_state.messages.append(msg)
        render_assistant(msg)
