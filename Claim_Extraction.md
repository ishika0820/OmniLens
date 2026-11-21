# Claim Extraction and Evaluation — OmniLens

## 1. Overview

OmniLens aims to identify factual differences between news articles covering the same event. The first stage of the pipeline involves extracting atomic factual claims from news articles, which are subsequently compared against a reference article to identify shared, new, and conflicting information.

An **atomic claim** is a self-contained factual statement expressing a single verifiable proposition.

To select a reliable claim extraction method, we experimented with multiple approaches and evaluated their outputs using four criteria:

- **Faithfulness:** Whether an extracted claim is factually supported by its source passage.
- **Atomicity:** Whether each claim expresses a single factual proposition.
- **Redundancy:** Whether multiple extracted claims repeat the same factual information.
- **Entity preservation:** Whether names, organizations, dates, and other important entities are accurately retained.

Our primary comparison focused on **FENICE and Stanford OpenIE**, followed by an additional evaluation using **Claude Haiku 5.5**.

---

## 2. Dataset

We used news articles from [DiverseSumm](https://github.com/salesforce/DiverseSumm), a multi-document news summarization dataset containing articles covering the same events.

For the claim extraction benchmark, we selected:

| Property | Value |
|---|---|
| Dataset | DiverseSumm |
| Events | 6 |
| Candidate articles | 30 |
| Evaluation unit | Article passages |
| FENICE claims extracted | 1,014 |
| Stanford OpenIE claims extracted | 3,897 |
| Claude Haiku claims extracted | 1,032 |

All extractors were evaluated using the same validation articles and source passages to support meaningful comparisons.

Claims were stored in CSV format, with one row per claim and identifiers linking each claim to its original passage and article.

---

## 3. Claim Extraction with FENICE

### 3.1 Model

We used the claim extraction component of [FENICE](https://github.com/Babelscape/FENICE), a framework originally developed for evaluating the factual consistency of generated summaries.

The pretrained claim extractor is available on Hugging Face:

`Babelscape/t5-base-summarization-claim-extractor`

FENICE uses a T5-based sequence-to-sequence model to convert source text into natural-language factual claims.

Unlike traditional Open Information Extraction methods, which extract subject-relation-object structures, FENICE generates complete sentences intended to preserve the factual meaning of the original passage.

### 3.2 Extraction Process

The extraction pipeline follows these steps:

1. Load the news articles and their associated passages.
2. Pass each source passage to the pretrained FENICE model.
3. Generate factual claims from the passage.
4. Separate the generated output into individual claims.
5. Associate each claim with its source article and passage.
6. Save the results in a structured CSV file.

Each claim is assigned an identifier to preserve its relationship with the original source text.

### 3.3 Output Format

The extracted claims are stored with the following information:

| Column | Description |
|---|---|
| `event_id` | Identifier of the news event |
| `article_id` | Identifier of the source article |
| `passage_id` | Identifier of the source passage |
| `claim_id` | Unique identifier for the extracted claim |
| `claim` | Extracted factual claim |
| `source_passage` | Original passage used for extraction |
| `source_url` | URL of the original news article |

This structure allows claims to be evaluated individually while retaining their source context.

---

## 4. Faithfulness Evaluation Using AlignScore

### 4.1 Evaluation Method

We used [AlignScore](https://github.com/yuh-zha/AlignScore) to evaluate whether the extracted claims were supported by their original source passages.

AlignScore is a learned factual consistency metric that measures the alignment between a claim and its supporting context.

For each extracted claim, we provided:

- **Context:** The original source passage.
- **Claim:** The factual statement extracted by FENICE.

We used the pretrained `AlignScore-base` checkpoint with a RoBERTa-base backbone and `nli_sp` evaluation mode.

### 4.2 Evaluation Process

Each claim was scored individually against its source passage. AlignScore produces a continuous score between 0 and 1, where higher values indicate stronger predicted factual alignment.

We calculated the following statistics:

- Mean AlignScore
- Median AlignScore
- Standard deviation
- Number of claims below a diagnostic threshold of 0.90

We also inspected low-scoring claims manually to identify potential factual errors and cases where the metric disagreed with the source evidence.

### 4.3 Results

| Extractor | Mean AlignScore |
|---|---:|
| Stanford OpenIE | 0.8924 |
| **FENICE** | **0.9781** |
| Claude Haiku 5.5 | 0.9022 |

FENICE achieved the highest average AlignScore among the evaluated extractors.

However, manual inspection revealed that some correctly supported claims received unexpectedly low scores, particularly when claims used different wording or made entities explicit using surrounding context.

Therefore, AlignScore was treated as an automated faithfulness indicator rather than definitive proof of factual correctness.

---

## 5. Redundancy Evaluation Using Sentence-BERT and Qwen

### 5.1 Objective

Redundancy occurs when multiple extracted claims express the same or substantially equivalent factual information.

For example:

- "Foot Locker plans to close approximately 400 stores by 2026."
- "Foot Locker intends to shut nearly 400 locations by 2026."

Although the wording differs, both claims communicate essentially the same fact.

Excessive redundancy increases the number of claims that downstream components must process without adding meaningful information.

### 5.2 Sentence-BERT Similarity Screening

We used Sentence-BERT to identify potentially redundant claims within the same source passage.

The procedure involved:

1. Converting each claim into a sentence embedding.
2. Computing cosine similarity between pairs of claims from the same passage.
3. Identifying highly similar pairs for further evaluation.

Sentence-BERT provides an efficient way to detect semantic overlap, but high similarity does not necessarily indicate factual duplication.

For example, two claims describing different numerical values or different entities may be semantically similar while representing distinct facts.

### 5.3 Qwen-Based Redundancy Evaluation

To distinguish genuine redundancy from semantic similarity, we also used **Qwen3-8B** to evaluate claim overlap.

The model was used to assess whether claims expressed the same factual information or contained meaningful differences.

This provided an additional semantic judgment beyond embedding similarity.

Using a locally hosted Qwen model allowed us to perform redundancy evaluation without incurring additional commercial API costs.

### 5.4 Results

| Extractor | Redundancy |
|---|---:|
| Stanford OpenIE | 63.51% |
| **FENICE** | **2.27%** |

FENICE produced substantially less redundant output than Stanford OpenIE.

The difference was also visible in the extraction volume: Stanford OpenIE generated 3,897 claims, compared with 1,014 from FENICE, on the same 30 articles.

Manual inspection suggested that many OpenIE outputs were fragmented or repeated similar information rather than introducing distinct factual propositions.

---

## 6. Claim Extraction Using Claude Haiku 5.5

### 6.1 Motivation

Following feedback on our initial extractor evaluation, we tested a commercial large language model to determine whether a paid LLM could produce more faithful claims than the open-source approaches.

We selected **Claude Haiku 5.5** because it offered a relatively inexpensive API-based alternative.

### 6.2 Extraction Process

Unlike FENICE, which processed individual passages, Haiku received the article's passages together in a single request.

Each passage was identified by its original passage ID. The extraction prompt instructed the model to generate claims that were:

- Atomic and self-contained
- Faithful to the source
- Nonredundant
- Explicit about entities and factual details

The model returned structured JSON containing each extracted claim and its associated passage ID.

The outputs were converted into a CSV with one row per claim.

### 6.3 Results

Haiku extracted **1,032 claims** from the validation dataset.

Its average AlignScore was **0.9022**, compared with **0.9781 for FENICE**.

Because Haiku received article-level context during extraction while faithfulness was evaluated against individual passages, some low-scoring claims contained details that were potentially supported elsewhere in the article but not explicitly present in their assigned passage.

This was considered when interpreting the automated scores.

---

## 7. Faithfulness Evaluation Using Claude Haiku

### 7.1 Motivation

Manual inspection of the AlignScore results identified cases where apparently faithful claims received very low scores.

To obtain a second assessment of faithfulness, we used Claude Haiku 5.5 as an LLM-based evaluator.

We evaluated claims extracted by both FENICE and Haiku using the same evaluation prompt and model.

### 7.2 Evaluation Method

For each claim, the evaluator received:

- The original source passage
- The extracted claim
- Instructions to judge factual support using only the provided passage

The evaluator returned one of three labels:

| Label | Meaning |
|---|---|
| `SUPPORTED` | The passage directly states or clearly entails the claim |
| `UNSUPPORTED` | The passage does not establish the claim |
| `CONTRADICTED` | The passage contains information incompatible with the claim |

The evaluator also returned a short explanation and supporting evidence where available.

We defined the **supported-claim rate** as:

**Supported-claim rate = (Number of SUPPORTED claims / Total evaluated claims) × 100**

This is a binary faithfulness measure derived from the three-way judgments. It is not numerically equivalent to AlignScore.

### 7.3 Results

| Extractor | Claims evaluated | Haiku-judged faithfulness |
|---|---:|---:|
| **FENICE** | 1,014 | **97.14%** |
| Claude Haiku 5.5 | 1,032 | 95.64% |

FENICE achieved a supported-claim rate 1.50 percentage points higher than Haiku under the same LLM-based evaluation method.

This was consistent with the direction of the AlignScore comparison, although the two evaluation methods produced different absolute scores.

### 7.4 Limitations

Haiku was used both to extract and evaluate its own claims, introducing the possibility of self-evaluation bias.

Additionally, the LLM-based evaluation was substantially slower than AlignScore, requiring over 30 minutes to evaluate approximately 1,000 claims through individual API requests.

For these reasons, we retained AlignScore as our primary automated faithfulness metric and used Haiku-based evaluation as a supplementary check.

---

## 8. Overall Extractor Comparison

The main Stanford OpenIE and FENICE evaluation produced the following results:

| Metric | Stanford OpenIE | FENICE |
|---|---:|---:|
| Faithfulness ↑ | 89.24% | **97.81%** |
| Atomicity ↑ | **84.20%** | 78.65% |
| Redundancy ↓ | 63.51% | **2.27%** |
| Entity preservation ↑ | 54.89% | **91.75%** |

FENICE outperformed Stanford OpenIE on three of the four evaluated metrics.

Although OpenIE achieved higher atomicity, manual inspection found that some of its outputs lacked sufficient context or formed incomplete factual statements.

FENICE produced more self-contained claims, higher factual alignment, and substantially lower redundancy.

The supplementary Haiku comparison also favored FENICE on the two faithfulness evaluation methods.

---

## 9. Final Model Selection

Based on the experimental results, **the original pretrained FENICE claim extractor was selected for the OmniLens pipeline**.

The decision was based on:

- Higher faithfulness than Stanford OpenIE and Claude Haiku under the evaluated methods.
- Substantially lower redundancy than Stanford OpenIE.
- Stronger entity preservation than Stanford OpenIE.
- Ability to run locally without commercial API charges.
- Suitability for integration with downstream claim classification.

While the experiments support FENICE as the preferred extractor for our current pipeline, faithfulness alone does not measure how completely an extractor covers all important facts in an article.

Further evaluation of coverage and downstream classification performance remains relevant.

---

## 10. Integration with OmniLens

The selected extractor forms the first stage of the OmniLens pipeline:

**News articles → FENICE claim extraction → Reference-based claim comparison → Shared / New / Conflicting classification → Source-linked results**

The extracted claims will be compared against a selected reference article using a Natural Language Inference (NLI) classifier.

The final application aims to help users identify factual agreement, additional information, and disagreements across news coverage while preserving links to the original sources.

---

## References

1. [FENICE — GitHub](https://github.com/Babelscape/FENICE)
2. [FENICE claim extractor — Hugging Face](https://huggingface.co/Babelscape/t5-base-summarization-claim-extractor)
3. [AlignScore — GitHub](https://github.com/yuh-zha/AlignScore)
4. [DiverseSumm — GitHub](https://github.com/salesforce/DiverseSumm)
5. [Sentence-Transformers](https://www.sbert.net/)
6. [Qwen — GitHub](https://github.com/QwenLM/Qwen3)
7. [Anthropic API Documentation](https://docs.anthropic.com/)