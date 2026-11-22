# II. Literature Review / Related Work

<!-- Citation keys used in this report. Every entry was checked against the publisher, ACL Anthology,
     arXiv or the authors' page on 22 Nov 2026, EXCEPT where marked VERIFY.
     salton1988term     Salton & Buckley 1988, IP&M 24(5):513-523
     robertson2009bm25  Robertson & Zaragoza 2009, FnTIR 3(4):333-389
     manning2008ir      Manning, Raghavan & Schuetze 2008, Introduction to IR (Cambridge UP)
     damerau1964        Damerau 1964, CACM 7(3):171-176
     karpukhin2020dpr   Karpukhin et al. 2020, EMNLP pp. 6769-6781
     thakur2021beir     Thakur et al. 2021, NeurIPS Datasets & Benchmarks track
     lewis2020rag       Lewis et al. 2020, NeurIPS 33  (page range 9459-9474: VERIFY, dblp blocked automated access)
     ji2023hallucination Ji et al. 2023, ACM Computing Surveys 55(12):1-38
     rashkin2023ais     Rashkin et al. 2023, Computational Linguistics 49(4):777-840
     gao2023alce        Gao et al. 2023, EMNLP pp. 6465-6488
     liu2023verifiability Liu, Zhang & Liang 2023, Findings of EMNLP pp. 7001-7025
     es2024ragas        Es et al. 2024, EACL System Demonstrations pp. 150-158
     neupane2024barkplug Neupane et al. 2024, arXiv:2405.08120
-->

SNU Central combines four lines of research: classical ranking functions, retrieval-augmented generation, attribution and hallucination in generated text, and question-answering assistants for universities. We review each and then state what is new in our approach.

## A. Term Weighting and Probabilistic Ranking

**Salton and Buckley** [@salton1988term] systematically compared term-weighting schemes for automatic text retrieval and showed that single terms with appropriate weights — combining within-document term frequency, inverse document frequency and length normalisation — retrieve better than more elaborate text representations. Their *tf·idf* weighting with cosine normalisation is the basis of our TF-IDF baseline.

**Robertson and Zaragoza** [@robertson2009bm25] present the Probabilistic Relevance Framework, from the binary independence model to **BM25** and its field-weighted extension BM25F. BM25 adds two ingredients that plain TF-IDF lacks: term-frequency *saturation* (controlled by $k_1$) and *document-length normalisation* (controlled by $b$). We implement BM25 exactly as derived there, and our experiments tune $b$ because our passages vary widely in length.

**Manning, Raghavan and Schütze** [@manning2008ir] give the textbook treatment of the inverted index, tf-idf vector-space scoring, the evaluation measures we use (precision, recall, F1 and mean reciprocal rank), and *isolated-term spelling correction* with a character *k*-gram index and edit distance. **Damerau** [@damerau1964] introduced the edit operation that treats a swap of two adjacent letters as a single error, which covers a large share of real typing mistakes; our query speller uses this Damerau–Levenshtein distance.

## B. Dense Retrieval and the Strength of BM25

**Karpukhin et al.** [@karpukhin2020dpr] proposed Dense Passage Retrieval (DPR), which encodes questions and passages with BERT and retrieves by inner product. Trained on open-domain QA data, DPR beats a Lucene BM25 baseline by 9–19 percentage points in top-20 retrieval accuracy. However, **Thakur et al.** [@thakur2021beir] showed with the BEIR benchmark (18 datasets, 10 retrieval systems) that when models are applied *zero-shot* to new domains, **BM25 remains a robust baseline**, and dense retrievers often generalise poorly; the best zero-shot results come from re-ranking models at high computational cost.

These two results justify our choice of retriever. University policy text is a new domain with no training data, and our system must run on an 8 GB laptop at no cost. A lexical BM25 retriever is therefore both the safest and the most practical first choice; dense or hybrid retrieval is left as future work.

## C. Retrieval-Augmented Generation

**Lewis et al.** [@lewis2020rag] introduced Retrieval-Augmented Generation (RAG): a pre-trained sequence-to-sequence generator conditioned on passages that a neural retriever selects from a Wikipedia index. RAG produced more specific and more factual answers than a generator alone and set the state of the art on open-domain QA. RAG trains the retriever and generator together; we keep the same retrieve-then-generate idea but with a classical retriever and an off-the-shelf open-weight LLM that is only prompted, never trained. This keeps the ranking step transparent and testable on its own.

## D. Hallucination, Attribution and Citations

**Ji et al.** [@ji2023hallucination] survey hallucination in natural language generation — output that is fluent but unfaithful to the source or to the world — across summarisation, dialogue, generative QA and machine translation, and review metrics and mitigations. Retrieval grounding is one of the main mitigations they discuss.

**Rashkin et al.** [@rashkin2023ais] define *Attributable to Identified Sources* (AIS): a generated statement is acceptable only if a reader could confirm it from an identified source. AIS motivates our **statement-level** grading: we check each answer statement against the passage it cites, not only the answer as a whole.

**Gao et al.** [@gao2023alce] built ALCE, a benchmark in which LLMs must answer with citations, and measured citation recall and precision automatically. Even the best models lacked complete citation support for about half of their answers on long-form questions. **Liu, Zhang and Liang** [@liu2023verifiability] audited four commercial generative search engines (Bing Chat, NeevaAI, perplexity.ai and YouChat) and found that only **51.5%** of generated sentences were fully supported by their citations, and only **74.5%** of citations supported the sentence they were attached to. These two studies are our main point of comparison for answer groundedness (Section VI).

## E. Evaluating RAG Systems

**Es et al.** [@es2024ragas] proposed RAGAS, a reference-free framework that scores a RAG pipeline on faithfulness, answer relevance and context relevance using an LLM as the judge. It made automatic RAG evaluation popular, but its scores depend on another LLM's judgement. We instead report standard IR metrics on hand-labelled relevance judgments, manual answer grading, and simple deterministic checks — for example, whether every number in an answer appears in a retrieved passage.

## F. Question-Answering Assistants for Universities

**Neupane et al.** [@neupane2024barkplug] built BarkPlug v.2, a RAG chatbot for Mississippi State University covering departments, financial aid, admissions, housing and other campus resources. They report a mean RAGAS score of 0.96 and a user-satisfaction study. Their system shows that RAG is useful in this setting. Its evaluation, however, is LLM-judged (RAGAS) and survey-based; the paper's summary does not report run-time verification of citations against the retrieved passages, or abstention before the LLM is called, which are the two properties we focus on.

## G. Novelty of Our Approach

Table I compares SNU Central with the closest work. Our contribution is not a new model but a **transparent, verifiable pipeline** for a high-stakes domain, together with an evaluation that measures exactly the properties students depend on.

**Table I. Comparison with related systems**

| | RAG [@lewis2020rag] | ALCE [@gao2023alce] | Generative search engines [@liu2023verifiability] | BarkPlug v.2 [@neupane2024barkplug] | **SNU Central (ours)** |
|---|---|---|---|---|---|
| Retriever | Dense (DPR), trained | Dense / web search | Web search | LLM-based RAG stack | **Our own BM25 / TF-IDF over an inverted index** |
| Citations in answer | No | Yes (generated by LLM) | Yes | Not reported | **Yes: LLM writes `[n]`, app builds the citation from metadata** |
| Citations verified against retrieved passages | — | Measured offline | Audited offline | — | **Every answer, at run time; invalid markers removed** |
| Abstains before calling the LLM | No | No | No | No | **Yes: BM25 confidence gate** |
| Links to the exact page of the source | No | No | URL only | Not reported | **Yes: document, page, section, paragraph, date** |
| Retrieval evaluation | QA accuracy | — | — | RAGAS | **P@5, R@5, F1@5, MRR on 92 labelled passages** |
| Answer evaluation | Exact match | Citation recall / precision | Human audit | RAGAS, SUS survey | **Manual correctness, completeness, statement-level support** |
| Cost / hardware | GPU training | Commercial LLMs | Commercial services | Hosted LLMs | **$0, 8 GB laptop, free-tier open-weight LLM** |

In short, SNU Central differs from prior work in four ways:

1. **The citation is produced by the application, not the model.** Because the LLM only writes passage numbers, it cannot invent a document name, page or section; the remaining risk — citing the wrong passage — is checked on every answer.
2. **Abstention happens before generation** when retrieval finds nothing relevant, so many off-topic questions never reach the LLM at all.
3. **The retriever is classical and inspectable**, as recommended by the BEIR findings for new domains, and is evaluated on its own with standard IR metrics.
4. **Groundedness is measured at the statement level** in the spirit of AIS, which allows a direct comparison with the 51.5% sentence-support rate reported for commercial generative search engines.
