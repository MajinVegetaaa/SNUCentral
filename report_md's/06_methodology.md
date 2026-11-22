# V. Methodology

This section gives the algorithms and formulas exactly as implemented. Notation: $N$ is the number of passages in the collection, $\mathrm{tf}_{t,d}$ the frequency of term $t$ in passage $d$, $\mathrm{df}_t$ the number of passages containing $t$, $|d|$ the length of passage $d$ in index terms, and $\overline{|d|}$ the average passage length.

## A. Text Analysis

One analyzer function is used both for indexing passages and for processing queries, so the two always produce comparable terms. It performs four steps:

1. **Normalisation and tokenisation.** Text is lower-cased and split with the pattern `[a-z0-9]+([-./][a-z0-9]+)*`, which keeps numbers, decimals, dates and hyphenated words intact (`75`, `3.5`, `15/10/2025`, `re-evaluation`). A hyphenated or slashed token is also indexed by its parts, so *evaluation* matches *re-evaluation*.
2. **Stop-word removal** with a hand-picked list of 74 words. Negations and modal verbs (*no, not, may, must, shall*) are deliberately kept, because in policy text they decide the meaning of a rule.
3. **Stemming** of alphabetic tokens with the Porter stemmer (*withdrawing → withdraw*, *courses → cours*). Numbers and mixed tokens are not stemmed.
4. **Versioning.** A hash of the stop-word list, the token pattern and the stemmer is stored in the index; if the analyzer changes, the old index is refused and must be rebuilt.

**Query expansion.** A hand-built SNU dictionary of 13 synonym and acronym groups (for example {*drop, withdraw, withdrawal*}, {*cgpa, cumulative grade point average*}, {*mess, dining*}) is applied to queries only: if any member phrase of a group occurs in the query, the analysed terms of all members are added.

## B. Passage Construction

Each PDF line carries its font size, weight and position. A line is a **heading** if it is short ($\le 12$ words), does not end like a sentence, and is either larger or bolder than the body text or begins with a section number (`4.2`, `A1.`, `SECTION A:`). A numbered line that reads as a sentence — it contains a verb or negation such as *is, are, will, must, not* — is a list item, not a heading; this rule stopped notes such as *"2. Tuition Fee Waiver not applicable for Sponsored Candidates"* from being mistaken for section titles. Open headings form a stack, and its contents become the passage's section path.

Paragraphs are grouped into passages of 40–300 words within one section. Passages whose normalised text is identical are merged, keeping the first and recording the others. The final collection has $N = 2{,}801$ passages.

## C. Inverted Index

For every term $t$ the index stores a postings list $\{d : \mathrm{tf}_{t,d}\}$, together with $\mathrm{df}_t$, every passage length $|d|$, $\overline{|d|}$, and the inverse document frequency used by TF-IDF,

$$\mathrm{idf}_t = \log_{10}\frac{N}{\mathrm{df}_t}. \tag{1}$$

Only the postings of query terms are read at search time, so scoring touches a small fraction of the collection.

## D. TF-IDF with Cosine Similarity (baseline)

Following Salton and Buckley [@salton1988term] and Manning et al. [@manning2008ir], a passage is represented by the weights

$$w_{t,d} = \left(1 + \log_{10}\mathrm{tf}_{t,d}\right)\cdot \mathrm{idf}_t, \tag{2}$$

and a query $q$ by $w_{t,q} = \mathrm{idf}_t$ for each distinct query term. Passages are ranked by the cosine of the angle between the two vectors,

$$\cos(q,d) = \frac{\sum_{t \in q \cap d} w_{t,q}\, w_{t,d}}{\sqrt{\sum_{t\in q} w_{t,q}^2}\;\sqrt{\sum_{t \in d} w_{t,d}^2}}. \tag{3}$$

Passage norms are computed once when the index is loaded.

## E. Okapi BM25

BM25 [@robertson2009bm25] scores passage $d$ for query $q$ as

$$\mathrm{BM25}(q,d) = \sum_{t \in q} \mathrm{idf}^{\mathrm{BM25}}_t \cdot \frac{\mathrm{tf}_{t,d}\,(k_1+1)}{\mathrm{tf}_{t,d} + k_1\left(1 - b + b\,\dfrac{|d|}{\overline{|d|}}\right)}, \tag{4}$$

$$\mathrm{idf}^{\mathrm{BM25}}_t = \ln\!\left(1 + \frac{N - \mathrm{df}_t + 0.5}{\mathrm{df}_t + 0.5}\right). \tag{5}$$

The parameter $k_1$ controls how quickly repeated occurrences of a term stop adding to the score (saturation), and $b$ controls how strongly long passages are penalised. We use $k_1 = 1.5$ and $b = 0.5$. The usual default $b = 0.75$ over-rewarded very short passages such as document title pages, because our passage lengths vary widely; the effect of this choice is reported in Section VI. The "+1" inside the logarithm keeps the weight positive for terms that occur in more than half of the passages. The top $K = 5$ passages are returned.

## F. Abstention Gate

Raw BM25 scores grow with the number and rarity of query terms, so a fixed threshold on the top score wrongly rejected short questions. We therefore normalise the top score by the highest score the query could reach, which is obtained when every query term is present and fully saturated ($\mathrm{tf} \to \infty$ makes the fraction in (4) approach $k_1+1$):

$$\mathrm{conf}(q) = \frac{\max_d \mathrm{BM25}(q,d)}{\sum_{t \in q,\ \mathrm{df}_t>0} \mathrm{idf}^{\mathrm{BM25}}_t\,(k_1+1)} \in [0, 1). \tag{6}$$

The system abstains **without calling the LLM** if (i) no query term occurs in the index, or (ii) $\mathrm{conf}(q) < \tau$. The threshold $\tau$ can be tuned on the evaluation set by choosing the value that maximises

$$\mathrm{Acc}(\tau) = \frac{|\{q \in A : \mathrm{conf}(q) \ge \tau\}| + |\{q \in U : \mathrm{conf}(q) < \tau\}|}{|A| + |U|}, \tag{7}$$

where $A$ and $U$ are the answerable and unanswerable questions. We deliberately set $\tau = 0.20$, below the tuned value, because a wrong refusal of a real policy question is worse than passing an off-topic question to the LLM, whose prompt instructs it to decline. The gate therefore acts as a first filter and the prompt as a second.

## G. Context Expansion

For each of the top passages, its preceding and following passages in the same document are candidates. Neighbours in the **same section** are added first, and neighbours from a **different section only if they are on the same page**, until at most 10 passages are sent. This brings in tables and list items that answer the question but share no words with it (the minimum-class-size table in Section IV-D). Retrieval metrics are always computed on the top five passages *before* this step.

## H. Grounded Generation and Citation Validation

The passages are numbered and wrapped in delimited blocks that carry their document name, section and date; the prompt states that text inside the blocks is data, not instructions. The model (`gpt-oss-120b`, temperature 0, low reasoning effort) must cite a passage number `[n]` after every claim. The prompt is versioned; version 4 is the result of the evaluation-driven revisions described in Section VI.

After the answer is complete, the application:

1. **normalises** marker variants such as `【3】` and `【3†L4-L5】` to `[3]`;
2. **validates** every marker: with $n$ passages sent, the sets of valid and invalid markers are
$$V = \{m : 1 \le m \le n\}, \qquad I = \{m : m < 1 \ \lor\ m > n\}; \tag{8}$$
invalid markers are removed and the answer is flagged; an answer with $V = \varnothing$ is shown as unverified;
3. **counts uncited sentences**, which by the requirements are treated as not established by the documents;
4. **builds each citation from metadata** (document, page, section, paragraph, date and a link to the PDF page), so the model never writes a document name or page number itself.

Answers in which the model states that the documents do not cover the question are recognised and shown as a refusal rather than as an uncited answer.

## I. Spelling Correction

Following the isolated-term correction method of Manning et al. [@manning2008ir]:

1. **Known words.** A query word is known if it, or its stem, occurs anywhere in the collection, or if it is in the synonym dictionary. Only unknown alphabetic words of at least four letters are corrected.
2. **Candidates.** Each vocabulary word seen at least twice is indexed by its character bigrams, with `$` marking the word boundaries (*cat* → {`$c`, `ca`, `at`, `t$`}). Candidates for a misspelling $w$ are vocabulary words $v$ whose bigram sets overlap with Jaccard coefficient
$$J(w,v) = \frac{|G(w) \cap G(v)|}{|G(w) \cup G(v)|} \ge 0.3, \tag{9}$$
plus every vocabulary word exactly one edit away from $w$, which catches swapped letters (*refnud*) that break bigram overlap.
3. **Distance.** Candidates are compared with the Damerau–Levenshtein distance [@damerau1964] (optimal string alignment), computed by dynamic programming over prefixes $a_{1..i}$, $b_{1..j}$:
$$D_{i,j} = \min\begin{cases} D_{i-1,j} + 1 & \text{(deletion)}\\ D_{i,j-1} + 1 & \text{(insertion)}\\ D_{i-1,j-1} + [a_i \ne b_j] & \text{(substitution)}\\ D_{i-2,j-2} + 1 & \text{if } a_i = b_{j-1},\ a_{i-1} = b_j \ \text{(transposition)} \end{cases} \tag{10}$$
4. **Selection.** A candidate is accepted only within distance 1 (words of up to five letters) or 2 (longer words). Ties are broken by preferring the same first letter and then the more frequent word.
5. **Off-topic guard.** If any unknown word has no acceptable candidate (*pizza*, *margherita*), the query is treated as using vocabulary the collection does not have, and nothing is corrected.

Because a word that occurs nowhere in the collection cannot match anything, the corrected query is searched directly, and the original wording stays one click away. Each correction takes 1–2 ms.

## J. Document Dates

A document's date is taken only from its own text, in this order: the latest release date in its *Release Control* table (or the ratification date if the release cell is empty); an explicit "Effective Date:", "effective from" or "with effect from" line; or "approved … in *Month Year*". Otherwise the date is left empty and shown as "date not stated". A citation from a document last revised more than three years earlier carries a warning.

## K. Evaluation Measures

**Retrieval.** For a query with relevant set $R$ and ranked list $L_K$ of the top $K$ passages,

$$P@K = \frac{|L_K \cap R|}{K}, \qquad R@K = \frac{|L_K \cap R|}{|R|}, \qquad F_1@K = \frac{2\,P@K \cdot R@K}{P@K + R@K}, \tag{11}$$

$$\mathrm{MRR} = \frac{1}{|Q|}\sum_{q \in Q} \frac{1}{\mathrm{rank}_q}, \tag{12}$$

where $\mathrm{rank}_q$ is the position of the first relevant passage (the term is 0 if none is retrieved). All measures are averaged over the queries; we use $K = 5$.

**Abstention.** Each question is either answered or declined, so abstention is a binary classification with the declined class as positive. We report accuracy, precision, recall and F1 of declining, with the counts of correct declines (TP), wrong declines of answerable questions (FP) and answered unanswerable questions (FN):

$$\mathrm{Acc} = \frac{TP + TN}{|Q|}, \quad P = \frac{TP}{TP+FP}, \quad R = \frac{TP}{TP+FN}, \quad F_1 = \frac{2PR}{P+R}. \tag{13}$$

**Answers.** Each answer to an answerable question is graded for *factual correctness*, *evidence support*, *citation accuracy* and *completeness* (all conditions and exceptions kept).

**Statement-level groundedness.** Following the attribution view of Rashkin et al. [@rashkin2023ais], each answer is split into statements (sentences and list items; headings skipped). A list item without its own marker inherits the marker that closes its list. The share of supported statements is

$$\mathrm{Groundedness} = \frac{|\{s : s \text{ is supported by a passage it cites}\}|}{|\{s\}|}, \tag{14}$$

where a statement without any citation counts as unsupported. To focus the manual check, each statement is first scored automatically by the share of its content stems that appear in the passages it cites,

$$\mathrm{WS}(s) = \frac{|\mathrm{stems}(s) \cap \mathrm{stems}(\text{cited passages})|}{|\mathrm{stems}(s)|}, \tag{15}$$

and statements with $\mathrm{WS}(s) < 0.6$ or no citation are read in full. A second deterministic check flags any number in an answer that appears in none of the passages sent to the model.

**Spelling robustness.** For every answerable query, two adjacent letters in the middle of its longest word are swapped; we report how many typos the speller restores and the MRR with and without correction.

**Latency.** Retrieval time is measured over 20 repetitions per query with the index in memory; answer time is measured end to end, from receiving the question to the end of the streamed answer.
