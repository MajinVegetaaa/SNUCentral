# III. Objective

The aim of SNU Central is to provide **a single platform through which students can ask questions about Shiv Nadar University's policies in their own words and receive clear answers that are supported by, and linked to, the original university documents.**

## A. Goals

Following the project brief, the system should make institutional information:

1. **Accessible** — documents from different university offices and categories (academic affairs, examinations, student affairs, finance, international office, administration) available through one interface.
2. **Searchable** — relevant passages found from a natural-language question, without the student knowing the document name or the policy's exact wording.
3. **Understandable** — formal policy language turned into short, plain answers that still keep every condition, exception, number and deadline.
4. **Verifiable** — every answer linked to the document, page, section and paragraph it came from, with a one-click link that opens the original PDF at that page.
5. **Reliable** — no unsupported answers: when the documents do not contain an answer, the system says so instead of guessing.

## B. Specific Objectives

To meet these goals, the project sets out to:

- **O1.** Build a corpus of official, publicly available SNU documents with full provenance (source URL, fetch date, document date) and split it into paragraph-level passages that keep their citation metadata.
- **O2.** Implement the core IR components ourselves — tokenisation, stop-word removal, stemming, an inverted index, TF-IDF with cosine similarity, and BM25 — so that ranking is transparent and testable without any LLM.
- **O3.** Compare TF-IDF and BM25 on a hand-labelled set of student questions using precision, recall, F1 and mean reciprocal rank (MRR).
- **O4.** Generate answers with an open-weight LLM *only* from the retrieved passages, with citations that are produced and checked by the application.
- **O5.** Detect questions that the documents cannot answer, and decline them, preferably before any LLM call.
- **O6.** Make search robust to the way students actually type, through synonym expansion and spelling correction.
- **O7.** Evaluate answer quality separately from retrieval quality: factual correctness, completeness, citation validity, abstention and statement-level groundedness.
- **O8.** Run on a student's laptop (8 GB RAM) at no running cost, and keep working — showing the relevant passages — when the LLM is unavailable.

## C. Success Criteria

The following targets were fixed in the requirements document before the system was evaluated:

**Table II. Targets set for the evaluation**

| Criterion | Target |
|---|---|
| Mean reciprocal rank of the better ranker | ≥ 0.70 |
| Precision@5 of the better ranker | ≥ 0.60 |
| Answer statements supported by a cited passage | ≥ 90% |
| Correct abstention on unanswerable or off-topic questions | ≥ 80% |
| Citations pointing to the correct document, page and paragraph | 100% |
| Retrieval time / complete answer time | < 500 ms / about 5 s |

## D. Research Questions

The evaluation in Section VI answers four questions:

- **RQ1.** Does BM25 retrieve more relevant policy passages than TF-IDF with cosine similarity on university documents?
- **RQ2.** Can a classical retriever with a simple confidence threshold separate answerable from unanswerable questions before calling an LLM?
- **RQ3.** When the LLM is restricted to numbered passages and its citations are checked by the application, what share of its statements are actually supported by the cited text?
- **RQ4.** How much retrieval quality is lost to spelling mistakes, and how much does edit-distance correction recover?

## E. Scope

The first version covers text-based PDF documents in English that are publicly available from four official sources. The following are outside its scope: scanned documents (OCR), documents that require an SNU login, dense or hybrid retrieval, conversational follow-up questions, and personalised eligibility decisions — the system states the criteria from the documents but never decides whether a particular student is eligible.
