# Manual Annotation Guidelines

## 1. Objective

The goal of this annotation task is to identify whether information presented in a news article is **NEW, SHARED, or CONFLICTING** compared to a reference article covering the same news event.

We use the **DiverseSumm dataset**, which contains multiple news articles covering the same event.

These annotations will help us study information novelty, overlap, and contradictions across news sources.

## 2. Dataset

- **Dataset:** [DiverseSumm](https://github.com/salesforce/DiverseSumm)
- Each event contains multiple news articles discussing the same event.
- For each selected event, **Article 1 is the reference article**.
- Articles 2–10 are candidate articles to compare against the reference.

For our initial pilot, we will annotate approximately **20–30 candidate claims across 5 different events**.

## 3. What Is an Atomic Claim?

An atomic claim is a single, independently verifiable statement that expresses one fact.

Each claim should:
- Contain only one main factual assertion.
- Be understandable without reading the entire article.
- Preserve important details such as people, dates, locations, and quantities.
- Avoid opinions or interpretations not explicitly supported by the article.

**Example**

Original sentence:

"DeSantis criticized Bragg's investigation and commented on Trump's alleged hush-money payment."

Break it into two atomic claims:

1. DeSantis criticized Bragg's investigation.
2. DeSantis commented on Trump's alleged hush-money payment.

These are separate claims because they describe different actions.

## 4. Annotation Labels

Each candidate claim must receive exactly one label.

### NEW

The candidate claim contains information that is **not stated or clearly implied** by the reference article.

Example:

- Reference: Trump faced a possible indictment in New York.
- Candidate: DeSantis accused Bragg of pursuing a political agenda.
- Label: **NEW**

The reference discusses the investigation but does not mention DeSantis making that accusation.

### SHARED

The candidate claim expresses the **same factual information** as a statement in the reference article, even if the wording differs.

Example:

- Reference: DeSantis was considered a potential rival to Trump for the 2024 Republican presidential nomination.
- Candidate: DeSantis was expected to run for president in 2024.
- Label: **SHARED**

Both statements communicate that DeSantis was a prospective presidential candidate.

### CONFLICTING

The candidate claim **directly contradicts** information stated in the reference article.

Example:

- Reference: The meeting took place on Monday.
- Candidate: The meeting took place on Tuesday.
- Label: **CONFLICTING**

Both statements refer to the same meeting but give incompatible dates.

**Important:** Different details do not automatically mean a conflict. A contradiction must concern the same entity, event, and factual attribute.

## 5. Annotation Procedure

**Step 1: Read the reference article**

Read Article 1 carefully to understand the event and identify its main factual claims.

**Step 2: Read the candidate article**

Read the assigned candidate article and identify approximately 3–5 important atomic claims.

**Step 3: Compare each claim**

For each candidate claim, determine whether the reference article contains equivalent, contradictory, or no corresponding information.

**Step 4: Assign a label**

Choose NEW, SHARED, or CONFLICTING using the definitions above.

**Step 5: Record reference evidence**

- For SHARED claims, record the matching claim or supporting sentence from Article 1.
- For CONFLICTING claims, record the contradicting claim or sentence from Article 1.
- For NEW claims, leave the reference evidence field blank or enter `N/A`.

**Step 6: Record uncertainty**

If a claim is difficult to classify, record the reason in the Notes column. Do not change the label based on another annotator's decision.

## 6. Annotation Spreadsheet Format

Each annotation should include:

| Column | Description |
|---|---|
| Event ID | Identifier of the DiverseSumm event |
| Reference Article ID | Article 1 |
| Candidate Article ID | Article being annotated |
| Claim ID | Unique identifier for the candidate claim |
| Candidate Claim | Atomic factual statement |
| Label | NEW / SHARED / CONFLICTING |
| Reference Evidence | Matching or contradicting claim from Article 1 |
| Notes | Explanation of uncertainty or ambiguity |
| Annotator ID | Team member identifier |

## 7. Team Annotation Rules

- All annotators must use the same reference article for each event.
- During the pilot, all annotators should independently label the **same set of candidate claims**.
- Do not discuss individual labels before completing the independent annotation.
- Do not look at another annotator's labels before submitting your own.
- Use only the reference article to determine whether a claim is NEW, SHARED, or CONFLICTING.
- Do not use external sources or personal knowledge to decide labels.
- Preserve uncertainty in the Notes column.

## 8. Inter-Annotator Agreement

After all team members complete their independent annotations:

1. Combine the individual annotation files.
2. Compare labels assigned to the same claim IDs.
3. Calculate inter-annotator agreement.
4. Discuss disagreements and clarify ambiguous guidelines.
5. Create an adjudicated annotation file containing the final agreed labels.

The final annotations will be stored in `annotations/adjudicated.csv`.

## 9. Important Considerations

- **Missing information is not conflicting information.** If the reference does not mention a fact, label it NEW.
- **Paraphrases can be SHARED.** Exact wording is not required.
- **The subject matters.** If Trump criticized a prosecutor in the reference, that does not mean a candidate claim saying DeSantis criticized the prosecutor is SHARED.
- **Keep claims atomic.** If a sentence contains multiple factual assertions, split it into separate claims.
- **Avoid unsupported assumptions.** Annotate only what the articles actually state.

---

*These guidelines are preliminary and may be updated after the initial annotation pilot and disagreement analysis.*
