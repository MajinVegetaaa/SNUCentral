# SNU Central: Project Overview

> **Tagline:** Your guide to university policies, procedures and information.
> Source: `IR Project_ Details.md`. This file is the short reference version of that document.

---

## 1. Problem Statement

Shiv Nadar University keeps its academic regulations, examination rules, hostel policies, fee guidelines, scholarship criteria, international-office procedures and official circulars on **many separate websites, portals and long PDF documents**.

The information usually exists. The hard part is **finding the right passage, understanding it and knowing which official provision it comes from.** Students end up opening several PDFs, scrolling through formal text or contacting different offices to answer simple questions.

### The specific problems

| # | Problem | What it means for a student |
|---|---|---|
| P1 | **Fragmented information** | Policies are spread across multiple websites, portals, documents and departments. There is no single place to look. |
| P2 | **Difficult document navigation** | Students must open long PDFs and find the relevant section or paragraph by hand. |
| P3 | **Keyword-dependent search** | Existing search only works if the student uses the same wording as the policy (e.g. "drop a course" vs "course withdrawal"). |
| P4 | **Hard-to-understand policies** | Official language is long, formal and technical, so it is hard to read quickly. |
| P5 | **No direct references** | Even when an answer is found, it is hard to identify the exact document and clause behind it. |

**One-line statement:**
*Students cannot efficiently locate, understand and verify university policy information because it is spread across many sources, written in formal language and searchable only by exact keywords.*

---

## 2. Requirements

> Derived from `IR Project_ Details.md`.
> **Priority:** **MVP** = required in the initial implementation · **Should** = target for the final version, built after the MVP works · **Future** = planned enhancement, not mandatory
> **Source:** the section of the project document the requirement comes from. *Research Xn* = added from the requirements research review (A = reliability, B = authenticity, C = scalability, D = user experience). Non-functional requirements are MVP unless marked otherwise.

### 2.1 Functional Requirements

#### FR-1 Document Collection

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-1.1 | The system shall maintain a collection of official, publicly accessible SNU documents from four sources: **S1** UG Handbook (academics), **S2** Student Handbook 2026 (regulations), **S3** an allow-list of student-relevant PDFs from the Mandatory Disclosure page, and **S4** the SNU Links Student Policies. URLs are listed in `system_design.md` §2. | MVP | §3.2, §7, Design §2 |
| FR-1.2 | Documents shall be organised by category (Academic Affairs, Examinations, Student Affairs, Hostel, Finance, International Office, University Circulars) in a structured directory. | MVP | §3.2 |
| FR-1.3 | The system shall record metadata for each document: title, filename, category, issuing department, publication/effective date and source URL/location. | MVP | §3.2 |
| FR-1.4 | Original document files shall be retained alongside their extracted text so they can be opened from citations. | MVP | §3.2 |
| FR-1.5 | Duplicate copies of the same document shall not be indexed. | MVP | §3.2 |
| FR-1.6 | Revised or superseded policies shall be identified. | Future | §3.2, §5.2 |
| FR-1.7 | A fetch step shall download all sources from their URLs (including PDFs embedded in SNU Links policy pages), record each document's URL, SHA-256 hash and fetch time, and report new, changed and removed documents so the index can be rebuilt. Documents are not fetched at query time. | MVP | Design §6 |

#### FR-2 Document Processing

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-2.1 | The system shall extract text from PDF documents automatically. | MVP | §3.3 Step 1, §7 |
| FR-2.2 | Extraction shall keep the document title, filename, page numbers, section headings and paragraph boundaries. | MVP | §3.3 Step 1 |
| FR-2.3 | The system shall support OCR for scanned PDFs. | Future (optional) | §3.3 Step 1 |
| FR-2.4 | The system shall clean extracted text by removing extra whitespace, headers, footers and formatting artefacts, and normalising text and punctuation. | MVP | §3.3 Step 2 |
| FR-2.5 | The system shall tokenize text, remove stop words where appropriate and apply stemming or lemmatization. | MVP | §3.3 Step 2 |
| FR-2.6 | Preprocessing shall keep important terms, numbers, dates and policy-specific terminology. | MVP | §3.3 Step 2 |
| FR-2.7 | Documents shall be divided into paragraph-level chunks. Short paragraphs may be merged or overlapped to keep context. | MVP | §3.3 Step 3 |
| FR-2.8 | Each chunk shall store `chunk_id`, `document_name`, `category`, `department`, `page_number`, `section`, `paragraph_id`, `text`, `publication_date`, `effective_date`, `is_superseded` and `source_url`/`file_path`. These fields support citations (FR-6.1), links to the original (FR-6.3), date warnings (FR-6.6) and the department note (FR-6.7). | MVP | §3.3 Step 3, Review |

#### FR-3 Indexing

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-3.1 | The system shall build an inverted index mapping terms to the chunks that contain them. | MVP | §3.3 Step 4 |
| FR-3.2 | The index shall store term frequency (TF) per chunk and document frequency (DF) across chunks, and compute inverse document frequency (IDF). | MVP | §3.3 Step 4 |
| FR-3.3 | The system shall compute TF-IDF vector representations of chunks. | MVP | §3.3 Step 4 |
| FR-3.4 | Indexing shall be done ahead of time, so queries do not reprocess the original PDFs. | MVP | §3.3 |

#### FR-4 Query Processing and Retrieval

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-4.1 | The system shall accept free-form natural-language questions. | MVP | §2.3(1) |
| FR-4.2 | Queries shall go through the same normalisation, tokenization, stop-word handling and stemming as the documents. | MVP | §3.4 Step 1 |
| FR-4.3 | The system shall rank chunks using TF-IDF with cosine similarity (baseline). | MVP | §3.4 Step 2 |
| FR-4.4 | The system shall rank chunks using BM25 (alternative ranking for comparison). | MVP | §3.4 Step 2 |
| FR-4.5 | The system shall return the top-K most relevant chunks with their relevance scores and metadata (default K = 5, configurable). | MVP | §3.4 Step 3 |
| FR-4.6 | The system shall expand queries using a hand-built SNU synonym and acronym dictionary (e.g. drop ↔ withdrawal, CGPA ↔ cumulative grade point average, mess ↔ dining). | MVP | §3.4 Step 1, Research D2 |
| FR-4.7 | The system shall support dense (semantic) retrieval using sentence embeddings. | Future | §3.4 Step 2 |
| FR-4.8 | The system shall support hybrid retrieval (keyword + dense) and re-ranking of retrieved passages. | Future | §3.4 Step 4, §5.2 |
| FR-4.9 | The system shall support weighting by document title, section and publication date/version. | Future | §3.4 Step 4 |
| FR-4.10 | The system shall allow results to be filtered by category/department. | Future | §3.4 Step 4, §5.2 |
| FR-4.11 | The system shall detect misspelled query terms and suggest corrections ("Did you mean…?") using edit distance against the index vocabulary. | Should | Research D3 |
| FR-4.12 | The system shall support document-discovery queries (e.g. "Which document contains the hostel leave policy?") by returning a ranked list of documents instead of a generated answer. | Should | §2.4, Research D4 |

#### FR-5 Answer Generation (RAG)

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-5.1 | The system shall send the user's question and the top-K retrieved passages (with metadata) to an existing open-weight LLM, by default the first model in Groq's free-tier list (currently `openai/gpt-oss-120b`), to generate an answer. | MVP | §3.5, Design ADR-001 |
| FR-5.2 | The LLM shall be called only after retrieval, and answers shall be based only on the retrieved passages. | MVP | §3.5, §3 Principles |
| FR-5.3 | Answers shall use simple language while keeping all conditions, exceptions, dates and eligibility requirements from the source. | MVP | §3.5, §2.3(3) |
| FR-5.4 | When the retrieved evidence is insufficient, the system shall say so explicitly instead of generating an unsupported answer (abstention). | MVP | §2.3(5), §3.5 |
| FR-5.5 | The LLM shall not invent document names, page numbers or paragraph references. | MVP | §3.5 |
| FR-5.6 | The system shall combine information from multiple relevant documents when a question requires it. | Future | §2.3(3), §5.2 |
| FR-5.7 | Where conflicting or multiple policy versions exist, the system shall identify the applicable document rather than silently merging provisions. | Future | §2.3(5), §5.2 |
| FR-5.8 | The system shall support LLM-based query rewriting or decomposition for complex questions. | Future | §5.2 |
| FR-5.9 | The system shall abstain without calling the LLM when the top retrieval score is below a threshold tuned on the evaluation set. | MVP | Research A1 |
| FR-5.10 | The system shall detect questions unrelated to SNU (e.g. general knowledge, essay writing) and decline them politely. | MVP | Research A3 |
| FR-5.11 | For eligibility questions, the system shall state the criteria from the documents and shall not decide whether a particular student is eligible, since it has no student data. | MVP | §2.4, Research B3 |
| FR-5.12 | If the LLM is unavailable or times out, the system shall still display the top-K retrieved passages with their citations. | MVP | §6(1), Research A2 |

#### FR-6 Source Referencing

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-6.1 | Every answer shall include references to its supporting sources: document name, page number, section heading and paragraph. | MVP | §2.3(4), §3.5 |
| FR-6.2 | The exact supporting paragraph text shall be displayed with the answer. | MVP | §3.5, §7 |
| FR-6.3 | The user shall be able to open the original document at the referenced page. | MVP | §2.3(4), §3.6 |
| FR-6.4 | Citations shall be produced from chunk metadata by the application code, not generated by the LLM. | MVP | §3.5, §5 |
| FR-6.5 | The LLM shall tag each statement with passage markers (e.g. [1], [2]). The application shall check that every marker refers to a retrieved passage, replace it with the full citation, and flag or reject answers containing invalid markers. Statements without a valid marker are treated as not established by the documents. | MVP | §2.3(5), Research B1 |
| FR-6.6 | Each citation shall show the document's publication or effective date. Documents older than a configured age, or marked superseded, shall carry a visible warning. | MVP | §3.2, Research B2 |
| FR-6.7 | Each answer shall include a short note to verify with the issuing department, naming the department from the document's metadata. | Should | Research B4 |

#### FR-7 User Interface

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-7.1 | The system shall provide a Streamlit chat interface where students type questions. | MVP | §3.6, §7 |
| FR-7.2 | The interface shall display the generated answer in a readable format. | MVP | §3.6 |
| FR-7.3 | The interface shall display source references and the supporting passages. | MVP | §3.6 |
| FR-7.4 | The interface shall provide a document viewer / link to the original document. | MVP | §3.6 |
| FR-7.5 | The interface shall display previous questions and answers within a session. Earlier messages are not used as context for new questions (see FR-7.6). | MVP | §3.6, §5.1 Stage 5, Review |
| FR-7.6 | The system shall support follow-up questions using conversational context. | Future | §2.3(1), §5.2 |
| FR-7.7 | The interface shall offer category filters. | Future | §3.6 |
| FR-7.8 | An admin mechanism shall allow adding, updating or removing documents from the knowledge base. | Future | §5.2 |
| FR-7.9 | Answers shall stream to the interface as they are generated. | MVP | Research D1 |
| FR-7.10 | Query terms shall be highlighted in the displayed supporting passages. | Should | Research D5 |
| FR-7.11 | The landing screen shall show example questions the user can click to ask. | Should | Research D6 |

#### FR-8 Evaluation

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-8.1 | A test set of 15–20 representative student queries shall be prepared, with relevant passages labelled manually, plus about 5 unanswerable or off-topic queries used to tune and test abstention (FR-5.9, FR-5.10). | MVP | §3.7A, Review |
| FR-8.2 | The system shall compute Precision@K, Recall@K and MRR for each retrieval method. | MVP | §3.7A |
| FR-8.3 | TF-IDF + cosine and BM25 (plus hybrid/dense, if implemented) shall be compared on the same query set. | MVP | §3.7A |
| FR-8.4 | Generated answers shall be manually evaluated for factual correctness, evidence support, citation accuracy, completeness and correct abstention. | MVP | §3.7B |
| FR-8.5 | Retrieval quality and answer quality shall be evaluated separately. | MVP | §3.5, §3.7 |
| FR-8.6 | The retrieval evaluation (P@K, Recall@K, MRR) shall be re-runnable as a script after every re-index or algorithm change, with results logged for comparison. | Should | Research A5 |
| FR-8.7 | The system shall log each query, the retrieved chunk IDs and scores, and the generated answer for debugging and evaluation. | Should | Research A6 |

---

### 2.2 Non-Functional Requirements

#### NFR-1 Accuracy and Reliability

| ID | Requirement | Source |
|---|---|---|
| NFR-1.1 | **Groundedness:** at least 90% of answer statements in the evaluation set must be supported by a cited retrieved passage, checked manually *(target provisional)*. This is the measurable form of FR-5.2. | §2.3(5), §3 Principles, Review |
| NFR-1.2 | **Source accuracy over fluency:** retrieving the right passage and citing it correctly takes priority over how well the answer reads. | §6(5) |
| NFR-1.3 | **Citation correctness:** every reference must point to the actual document, page and paragraph the information came from. | §3.7B |
| NFR-1.4 | **Accuracy over assumptions:** when unsure, the system must decline rather than guess. | §3 Principles |
| NFR-1.5 | **Authoritative sources:** only official SNU sources should be indexed. | §3.2 |
| NFR-1.6 | **Reproducibility:** generation shall use temperature 0 and a versioned prompt template, so the same question on the same index gives the same answer. *(Should)* | Research A4 |
| NFR-1.7 | **Graceful degradation:** failure of the LLM layer shall not make the system unusable; retrieval results remain available. | §6(1), Research A2 |

#### NFR-2 Traceability and Transparency

| ID | Requirement | Source |
|---|---|---|
| NFR-2.1 | Source metadata (document, page, section, paragraph) must be kept through every stage of preprocessing, indexing and retrieval. | §6(2) |
| NFR-2.2 | The provenance of every document (where it was obtained) must be recorded. | §3.2 |
| NFR-2.3 | Core IR logic (inverted index, TF-IDF, BM25 scoring) must be implemented or exposed clearly enough to show how it works. It must not be hidden inside a pre-built RAG framework. | §6(3), §5 |
| NFR-2.4 | **Legitimate sourcing:** only publicly accessible documents shall be collected. Site terms shall be respected, and no content behind a login or marked internal shall be indexed. | §3.2, Review |

#### NFR-3 Maintainability and Modularity

| ID | Requirement | Source |
|---|---|---|
| NFR-3.1 | The system shall be modular: document processing, indexing, retrieval, LLM integration and interface are separate components. | §6(4), §3 |
| NFR-3.2 | The IR engine must run and be testable on its own, without any LLM integration. | §6(1) |
| NFR-3.3 | The codebase shall be version-controlled with Git/GitHub. | §4 |
| NFR-3.4 | The IR core shall have unit tests: tokenizer and preprocessing, inverted index construction, and TF-IDF, cosine and BM25 scores checked against hand-computed values on a small toy corpus using the lecture formulas. | Review |
| NFR-3.5 | The project shall include a README covering installation, building the index, running the app and running the evaluation, so graders and teammates can reproduce the system. | Review |

#### NFR-4 Extensibility and Portability

| ID | Requirement | Source |
|---|---|---|
| NFR-4.1 | New documents and categories/departments can be added without rebuilding the application. | §3 Principles, §6(6) |
| NFR-4.2 | New retrieval algorithms can be added and compared against existing ones. | §6(6) |
| NFR-4.3 | The LLM provider (Groq, local Ollama, Azure OpenAI, OpenAI or Claude API) must be swappable without changing the retrieval code. | §3.5, §6(6) |
| NFR-4.4 | Tunable settings (K, BM25 k1 and b, chunk size, abstention threshold, LLM provider and model) shall live in a single configuration file, not in code. | Research C2 |
| NFR-4.5 | The application shall be containerised (Dockerfile + dependency file) so it runs the same locally and on a cloud host such as Azure. *(Should)* | Research C4 |

#### NFR-5 Usability

| ID | Requirement | Source |
|---|---|---|
| NFR-5.1 | **Simplicity:** students can get answers without navigating complicated interfaces or knowing document names or exact policy terms. | §3 Principles, §2.3(1) |
| NFR-5.2 | The interface centres on asking a question and seeing an evidence-backed answer. Extra features must not clutter it. | §3.6 |
| NFR-5.3 | Answers should be written in clear, concise, non-technical language. | §1.4, §2.3(3) |

#### NFR-6 Performance

| ID | Requirement | Source |
|---|---|---|
| NFR-6.1 | Retrieval shall use the prebuilt index and not reprocess the document collection per query. | §3.3, §3.3 Step 4 |
| NFR-6.2 | The system shall run locally with `streamlit run` (no cloud deployment) on the **reference machine**: a MacBook Air M1 with 8 GB RAM. The LLM is called through the Groq API, so no model runs on the laptop. | §3.5, §3.6, Design §1 |
| NFR-6.3 | The built index shall be saved to disk and loaded at startup, not rebuilt on every run. | Research C1 |
| NFR-6.4 | **Latency targets (provisional):** retrieval under 500 ms; first answer text within about 3 s; complete answer within about 5 s (Groq), measured on the reference machine (NFR-6.2). *(Should)* | Research C5, Design ADR-001 |

#### NFR-7 Cost and Infrastructure Constraints

| ID | Requirement | Source |
|---|---|---|
| NFR-7.1 | The initial version shall have no running cost: use a free-tier hosted open-weight model (Groq) rather than paid APIs. Local Ollama remains an optional fallback. The API key is kept in an environment variable or Streamlit secrets, never in the repository. | §3.5, Design ADR-001 |
| NFR-7.2 | No vector databases, multi-agent systems or orchestration frameworks shall be added until the baseline retrieval pipeline works. | §7 |
| NFR-7.3 | No custom language model will be trained. An existing model is used. | §3.5 |
| NFR-7.4 | The backend shall be implemented in Python. | §4, §7 |

#### NFR-8 Academic Integrity

| ID | Requirement | Source |
|---|---|---|
| NFR-8.1 | All AI assistance used during development (e.g. Claude Code) shall be declared in the final submission. | §4 |

#### NFR-9 Privacy

| ID | Requirement | Source |
|---|---|---|
| NFR-9.1 | Interaction logs shall not store personal or identifying information about users. *(Should)* | Research A6 |

---

### 2.3 Requirement → Problem Traceability

| Problem (Section 1) | Addressed by |
|---|---|
| P1 Fragmented information | FR-1.1, FR-1.2, FR-3.1, NFR-4.1 |
| P2 Difficult document navigation | FR-2.7, FR-4.5, FR-6.2, FR-6.3 |
| P3 Keyword-dependent search | FR-4.1, FR-4.2, FR-4.6, FR-4.7, FR-4.11 |
| P4 Hard-to-understand policies | FR-5.1, FR-5.3, NFR-5.3 |
| P5 No direct references | FR-6.1 – FR-6.7, NFR-1.3, NFR-2.1 |
| Unsupported or misleading answers (Section 3, "Reliable") | FR-5.4, FR-5.9 – FR-5.12, FR-6.5, FR-6.6, NFR-1.1, NFR-1.7 |

---

## 3. What We Are Building

**SNU Central** is a **centralised information retrieval and question-answering system** for Shiv Nadar University documents.

> A student asks a university-related question in their own words. SNU Central retrieves the most relevant passages from official documents, generates a clear answer grounded only in those passages, and shows the **exact source: document, page, section and paragraph**. If the documents do not support an answer, the system says so.

It combines two parts:

1. **A traditional IR engine (the core):** a custom inverted index, TF-IDF with cosine similarity, and BM25 ranking over paragraph-level chunks of university documents.
2. **An LLM layer (RAG):** an open-weight LLM accessed through the Groq API (swappable via config) that rewrites the retrieved passages into a readable answer. It may not add information that is not in those passages.

### How each problem is addressed

| Problem | How SNU Central addresses it |
|---|---|
| P1 Fragmented information | One indexed collection of documents across all departments |
| P2 Difficult navigation | Paragraph-level chunking and top-K passage retrieval |
| P3 Keyword dependence | Natural-language queries, query processing, an SNU synonym dictionary for query expansion, and spelling correction |
| P4 Hard to understand | LLM-generated plain-language answers that keep conditions and exceptions |
| P5 No references | Metadata-based citations: document, page, section, paragraph, link to original |

### What the system must be

- **Accessible:** one platform for information from all university domains.
- **Searchable:** finds information without the user knowing the exact document or keywords.
- **Understandable:** turns formal policy language into clear, concise answers.
- **Verifiable:** every answer is traceable to the document, page, section and paragraph.
- **Reliable:** declines to answer when the documents do not support an answer.

---

## 4. Scope

### In scope (initial version / MVP)

- [x] A collection of roughly 20–50 official SNU documents, organised by category
- [x] Automated PDF text extraction and preprocessing
- [x] Paragraph-level chunking with document metadata
- [x] Custom inverted index and TF-IDF + cosine similarity retrieval
- [x] BM25 ranking for comparison
- [x] Top-K relevant passage retrieval
- [x] Integration with an open-weight LLM through the Groq API
- [x] Fetch step that downloads sources S1–S4 with change detection
- [x] Natural-language answers grounded in retrieved evidence, with abstention
- [x] Document, page, section and paragraph-level references
- [x] A working Streamlit chat interface
- [x] A manually labelled query set (15–20 queries) evaluated with P@K, Recall@K and MRR
- [x] Query expansion with an SNU synonym and acronym dictionary
- [x] Score-threshold abstention and out-of-domain question handling
- [x] Statement-level citation markers checked against the retrieved passages
- [x] Source dates shown with citations; criteria-only answers to eligibility questions
- [x] Retrieval-only fallback when the LLM is unavailable
- [x] Streaming answers
- [x] Index saved to disk and all settings in one config file

### Planned for final version (Should)

- [x] Spelling correction ("Did you mean…?"): built as "Showing results for … (corrected from …)"
- [ ] Document-discovery queries (not built)
- [x] "Verify with [department]" note on answers
- [x] Term highlighting and example questions in the interface
- [x] Re-runnable evaluation script and anonymous interaction logging
- [x] Reproducible generation (temperature 0, versioned prompt)
- [ ] Docker container for cloud deployment (not built)
- [x] Latency targets (measured, see §5)

### Out of scope for now (future enhancements)

- Conversational memory / follow-up questions
- Policy version management
- Dense / hybrid retrieval and re-ranking
- Cross-document answer synthesis
- LLM-based query rewriting
- Admin document management
- Department-based filtering

### Not doing

- Training or fine-tuning our own language model
- Relying on pre-built RAG frameworks for the core retrieval logic
- Vector databases, agents or orchestration frameworks before basic retrieval works

---

## 5. Success Criteria

**Expected outcome:** A student enters a university-related question, receives an answer generated from relevant official documents, can inspect the exact supporting paragraphs, and can open the original document.

**Measured by:**

1. **Retrieval quality:** Precision@K, Recall@K and MRR on a hand-labelled query set, comparing TF-IDF vs BM25.
2. **Answer quality** (manual review): factual correctness, evidence support, citation accuracy, completeness (conditions and exceptions kept) and correct abstention.

**Provisional targets** (to be confirmed once the TF-IDF baseline has been measured):

| Metric | Target |
|---|---|
| MRR (best retrieval method) | ≥ 0.7 |
| Precision@5 | ≥ 0.6 |
| Supported answer statements (NFR-1.1) | ≥ 90% |
| Correct abstention on unanswerable / off-topic queries | ≥ 80% |
| Citation accuracy (correct document, page and paragraph) | 100% of displayed citations |

**Measured (22 Nov 2026, BM25, prompt v4; details in `README.md` and `system_design.md` §12):**

| Metric | Target | Result | Met? |
|---|---|---|---|
| MRR (best retrieval method) | ≥ 0.7 | 0.792 (TF-IDF 0.581) | ✅ |
| Precision@5 | ≥ 0.6 | 0.580 (TF-IDF 0.430) | ❌ just below |
| Supported answer statements (NFR-1.1) | ≥ 90% | 85/90 statements = 94% (14 read, 76 auto-passed; uncited statements count as unsupported) | ✅ |
| Correct abstention on unanswerable / off-topic queries | ≥ 80% | 5/5, with 0/20 false abstentions on answerable queries | ✅ |
| Citation accuracy | 100% | 20/20 answers, no invalid markers | ✅ |
| Latency (NFR-6.4) | < 500 ms retrieval; ~3 s first text; ~5 s full answer | retrieval median 0.2 ms; full answer median 0.9 s, max 1.5 s (`gpt-oss-120b`) | ✅ |

Completeness (conditions and exceptions kept) was 13/20 and is the weakest criterion; most gaps are passages that retrieval did not find.

> **Guiding principle:** The most important milestone is not a sophisticated chatbot. It is a **reliable retrieval engine** that consistently finds the correct university policy and the exact paragraph that supports the answer.
