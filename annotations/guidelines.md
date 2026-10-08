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
- For NEW claims, leave the reference evidence field blank
