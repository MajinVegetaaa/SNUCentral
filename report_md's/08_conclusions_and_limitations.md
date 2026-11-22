# VII. Conclusions and Limitations

## A. Conclusions

This paper presented **SNU Central**, a question-answering system that lets students ask about Shiv Nadar University's policies in plain words and receive answers built only from the official documents, with every claim linked to the document, page, section and paragraph it came from. The system combines a classical retrieval engine that we implemented ourselves with an open-weight LLM that is used only to phrase answers from retrieved passages.

The evaluation answers the four research questions set in Section III:

- **RQ1 — Retrieval.** On a hand-labelled set of 20 student questions over 39 policy documents, BM25 clearly outperforms TF-IDF with cosine similarity (MRR 0.792 vs 0.581, F1@5 0.609 vs 0.453), and is never worse on any question. Two inexpensive changes — merging duplicate passages and reducing BM25's length normalisation to $b = 0.5$ for passages of very uneven length — gave most of the improvement, while appending titles to passages and broadening the synonym dictionary made results worse. This supports the view that a well-tuned lexical ranker is a strong and practical choice for a new domain without training data.
- **RQ2 — Abstention.** A simple length-normalised BM25 confidence threshold stops two of five off-topic questions before any LLM call and never refuses a real one; together with a prompt instruction to decline, the system declined all five unanswerable questions and wrongly refused none of the twenty answerable ones.
- **RQ3 — Groundedness.** Restricting the model to numbered passages, building citations from metadata and checking every marker produced answers in which **94% of statements (85/90) are supported by a cited passage, and every cited statement is supported by the passage it cites**, with 95% of answers factually correct. Supplying neighbouring passages as context cut wrong refusals from four to none, and each prompt revision addressed a specific failure found in the evaluation.
- **RQ4 — Spelling.** A k-gram index with Damerau–Levenshtein distance restored all 20 test typos and recovered the full retrieval loss they caused (MRR 0.629 → 0.792), without altering any correctly spelled question.

Beyond the numbers, the project shows that a useful, verifiable assistant for institutional documents does not require large infrastructure: SNU Central runs on an 8 GB laptop, answers in under two seconds, costs nothing to run, and still shows the relevant cited passages when the LLM is unavailable. The most important design decision was to keep the **retrieval step transparent and separately evaluated** — every improvement and every failure in the final system could be traced to retrieval or to generation, and measured.

## B. Limitations

1. **Small, single-annotator evaluation.** The test set has 25 questions and 92 relevance judgments, labelled by one author with AI assistance. The relevance pools were built from our own two rankers, which may overstate recall, and BM25's $b$ parameter and prompts v2–v4 were tuned on the same questions they were evaluated on. The reported numbers are therefore somewhat optimistic and should be confirmed on a larger, independently labelled set.
2. **Completeness is the weakest result (13/20).** Most incomplete answers are retrieval misses: passages that hold the answer but share few words with the question — penalty lists, a fourth-year exception, tables — are not retrieved. This is the known vocabulary-mismatch weakness of lexical retrieval.
3. **Tables and document structure.** PDF tables are extracted as flat text (for example, grade-conversion tables become *"A+ A A A A- A …"*), and programme headings missing from the source PDF lead to misleading section paths. Our one factual error (Q08) comes from this: a refund rule for one certificate programme was presented as the default.
4. **Groundedness grading is partly automatic.** Of the 90 statements, 14 were read in full against their passages and 76 passed an automatic word-support check; a statement can share most of its words with a passage and still misstate it.
5. **Abstention depends on the LLM.** The gate alone catches only two of five off-topic questions; the rest are declined by the model following its instructions. A weaker or different model may not decline as reliably.
6. **Dependence on a free hosted model.** Groq's free tier limits `gpt-oss-120b` to 200,000 tokens per day. Beyond it the system falls back to `gpt-oss-20b`, which cited correctly in only 16–17 of 20 answers. Model names and limits can also change without notice.
7. **Coverage.** The collection holds 39 text-based English PDFs from four public sources. Scanned documents, documents behind an SNU login, web pages, circulars and announcements are not included, and five documents state no date, so their citations cannot warn about old versions.
8. **No conversation memory or personalisation.** Each question is answered independently, and the system states eligibility criteria but cannot decide whether a particular student is eligible.
9. **Deployment restrictions.** The SNU Links policies may not be stored in a retrieval system without the university's permission, so the system is intended for local use by SNU students and cannot be deployed publicly as is.

## C. Future Work

- **Hybrid retrieval:** add a dense retriever alongside BM25 and fuse their rankings, to reduce vocabulary mismatch.
- **Structure-aware ingestion:** parse tables as tables and recover programme and section headings, to fix the table and Q08-type failures.
- **A larger evaluation:** more questions written by students, relevance judged by several annotators, and a held-out test split for tuning.
- **Automatic per-statement verification at run time:** check each answer sentence against its cited passage with an entailment model and flag unsupported sentences in the interface.
- **Conversational follow-up questions, document-discovery queries ("which document covers …"), and filters by category or department.**
- **Version management:** detect superseded policies and prefer the latest applicable document.
- **An official deployment** with the university's permission, a scheduled document refresh, and a paid or self-hosted LLM to remove the free-tier limit.
