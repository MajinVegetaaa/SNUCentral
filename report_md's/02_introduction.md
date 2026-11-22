# I. Introduction

<!-- Citation keys like [@lewis2020rag] are resolved in 03_literature_review.md / 09_references.md.
     Every key used here must appear there. -->

## A. Background

Universities govern student life through a large body of institutional documents: academic regulations, attendance and grading policies, examination manuals, codes of conduct, fee policies, hostel rules and official circulars. At Shiv Nadar University (SNU), these documents are spread across several platforms — the university website, the SNU Links policy portal, handbooks and individual PDF circulars — and many of them run to dozens of pages; the university fee policy alone is 198 pages long.

The information students need is usually *present* in these documents. The difficulty lies in **locating, accessing and understanding** it efficiently. A student who wants to know the minimum attendance needed to sit an examination, how to change their major, or whether tuition fees are refunded after withdrawal must first guess which document holds the answer, then search a long PDF for the right clause, and then interpret formal policy language — or contact an office and wait for a reply.

## B. Importance of the Problem

The project brief identifies five concrete problems with the current process:

1. **Fragmented information:** policies are distributed across multiple websites, portals, documents and departments.
2. **Difficult document navigation:** students must open lengthy PDFs and manually locate the relevant section or paragraph.
3. **Keyword-dependent searching:** ordinary document search only works when the student knows the policy's own wording; a question phrased differently ("drop a course" versus "withdrawal") is easily missed.
4. **Hard-to-understand policies:** official documents use long, formal and technical language.
5. **No direct references:** even when an answer is found, identifying the exact document and provision that supports it is difficult.

These problems matter because policy questions have consequences: a student who misreads an attendance rule can be barred from an examination, and one who misunderstands a refund clause can lose money. An assistant for this setting therefore has a stricter requirement than a general chatbot: **every answer must be traceable to the official text, and the system must say so when the documents do not contain an answer** rather than produce a plausible-sounding one.

## C. Motivation

Large Language Models (LLMs) can turn formal policy text into clear, conversational answers, but on their own they are unsuitable for institutional questions: they have no knowledge of a particular university's rules and are prone to *hallucination* — fluent statements that are not supported by any source [@ji2023hallucination]. Retrieval-Augmented Generation (RAG) addresses this by retrieving relevant passages first and conditioning the model's answer on them [@lewis2020rag]. However, a RAG system is only as reliable as its retrieval step, and a generated answer is only verifiable if its citations can be checked [@gao2023alce].

This motivates the central design principle of SNU Central, taken from the project brief: **retrieval before generation, source transparency, and accuracy over assumptions.** We deliberately build the retrieval core from classical, inspectable information-retrieval techniques — an inverted index with TF-IDF and BM25 ranking [@salton1988term; @robertson2009bm25] — rather than hiding it inside a framework, and we treat the LLM as a thin language layer that may only rephrase what retrieval has found. The project also explores how far such a system can go under realistic student constraints: a single developer, an 8 GB laptop, and a running cost of zero.

## D. Contributions

The main contributions of this work are:

1. **A curated, citable corpus of official university documents.** We collect 39 publicly available SNU policy documents from four official sources, with automatic change detection, and split them into 2,801 paragraph-level passages that each keep their document, page, section, paragraph and date. Document dates are read from the documents themselves (for example, the release-control table of each policy), which dates 34 of the 39 documents without guessing.

2. **A from-scratch IR engine with a measured comparison.** We implement an inverted index, TF-IDF with cosine similarity, and Okapi BM25, and compare them on a hand-labelled test set. BM25 reaches an MRR of 0.792 against 0.581 for TF-IDF. Each design change (duplicate merging, length normalisation, heading detection) was kept or rejected on the basis of this evaluation.

3. **Citation-grounded generation with verification.** The LLM only writes passage markers such as `[3]`; the application, not the model, turns them into citations from passage metadata and rejects markers that point to no retrieved passage. Neighbouring passages are supplied as context so that answers held in tables are not missed.

4. **Two-layer abstention.** A length-normalised BM25 confidence gate stops clearly off-topic questions before any LLM call, and the prompt instructs the model to decline the rest. All five unanswerable or off-topic test questions are declined, with no false abstentions on the twenty answerable ones.

5. **Spelling correction for queries** using a character k-gram index and Damerau–Levenshtein edit distance. It restores 20 of 20 typo-corrupted test queries and recovers the full retrieval quality (MRR from 0.629 back to 0.792).

6. **A two-level evaluation of answer quality.** Beyond retrieval metrics (precision, recall, F1 and MRR), we grade generated answers for correctness and completeness and measure **statement-level groundedness**: 85 of 90 answer statements (94%) are supported by a cited passage.

7. **A working, low-cost system.** SNU Central runs locally as a Streamlit application on a MacBook Air M1 with 8 GB of RAM, uses an open-weight model (`gpt-oss-120b`) through Groq's free tier, answers in under two seconds, and degrades gracefully: without the LLM it still shows the relevant passages with their citations.

## E. Organisation of the Paper

Section II reviews related work on ranking functions, retrieval-augmented generation, attribution and hallucination. Section III states the objectives. Section IV presents the proposed system and its pipeline. Section V describes the methodology, algorithms and formulas. Section VI reports the dataset, experiments and results, including a comparison with published work. Section VII concludes and discusses limitations.
