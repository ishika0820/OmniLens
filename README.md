# OmniLens

**Cross-Article News Analysis Using NLP and Large Language Models**

OmniLens is an NLP-powered news analysis application that helps users understand how different news sources report the same event. Given a reference news article, OmniLens discovers related coverage, extracts factual claims, and compares those claims against the reference article.

The application categorizes claims into three classes:

- **SHARED:** The claim is supported by information in the reference article.
- **NEW:** The claim introduces information not established by the reference article.
- **CONFLICTING:** The claim contradicts information in the reference article.

These labels describe relationships between articles, not whether a claim is objectively true or false.

## 1. How OmniLens Works

The application follows this pipeline:

```text
User submits a reference article URL
                |
                v
        Event Registry API
    (News discovery and retrieval)
                |
                v
       Article Preprocessing
  (Cleaning and duplicate filtering)
                |
                v
       FENICE Claim Extraction
      (T5-based extraction)
                |
                v
        Claim Preprocessing
   (Fragment and duplicate removal)
                |
                v
     Claude Claim Classification
      (SHARED / NEW / CONFLICTING)
                |
                v
         OmniLens Results
   (Source evidence and comparisons)
```

### Components

**News Discovery — Event Registry**

Event Registry identifies the event associated with a reference article and retrieves related English-language news articles. The application selects articles from different publishers and filters near-duplicate content.

**Article Cleaning**

Article preprocessing removes common webpage boilerplate and unrelated content before claim extraction.

**Claim Extraction — FENICE**

OmniLens uses the pretrained `Babelscape/t5-base-summarization-claim-extractor` model to extract individual factual claims from related articles. Long articles are split into smaller chunks before processing.

**Claim Classification — Claude**

Claude compares extracted claims against the reference article and assigns SHARED, NEW, or CONFLICTING labels. The classification component uses a prompt template and few-shot examples.

**Backend — FastAPI**

FastAPI connects the different components and exposes the analysis pipeline through API endpoints.

## 2. Repository Structure

```text
OmniLens/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── news_provider.py
│   │   ├── article_cleaner.py
│   │   ├── claim_extractor.py
│   │   ├── claim_cleaner.py
│   │   ├── claim_annotator.py
│   │   ├── pipeline.py
│   │   ├── schemas.py
│   │   ├── index.html
│   │   └── prompts/
│   │       ├── classification_prompt.txt
│   │       └── few_shot_examples_train_20ex.json
│   ├── tests/
│   └── requirements.txt
├── frontend/                  # Planned frontend integration
├── annotations/               # Annotation guidelines
├── claim_extraction/          # Model evaluation notebooks
├── data/                      # Research datasets
├── Claim_Extraction.md
├── README.md
└── .gitignore
```

The research notebooks and datasets are kept separate from the application code.

## 3. Prerequisites

Before running OmniLens, install or obtain:

- Python 3.11
- Git
- An Event Registry API key
- An Anthropic API key for Claude
- An internet connection for news retrieval and model downloads

The FENICE model is downloaded automatically from Hugging Face when first initialized.

## 4. Installation

### Step 1 — Clone the repository

```bash
git clone https://github.com/ishika0820/OmniLens.git
cd OmniLens
```

For the integration version:

```bash
git fetch origin
git switch --track origin/integration-final
```

If the integration branch has not yet been pushed, use the local `integration-final` branch instead.

### Step 2 — Navigate to the backend

```bash
cd backend
```

### Step 3 — Create a virtual environment

**macOS/Linux:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Verify:

```bash
python --version
```

Expected: Python 3.11.x.

### Step 4 — Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Check for dependency conflicts:

```bash
python -m pip check
```

The installation includes the dependencies for Event Registry, article processing, FENICE, Claude, and FastAPI.

## 5. Environment Variables

Create a `.env` file inside `backend/`.

```env
EVENTREGISTRY_API_KEY=your_eventregistry_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

API keys can be obtained from:

- Event Registry: https://newsapi.ai/
- Anthropic: https://console.anthropic.com/

**Never commit API keys to GitHub.** Ensure `.env` is excluded by `.gitignore`.

## 6. Running the Application

From the `backend/` directory, with the virtual environment activated:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open the application in your browser:

**http://127.0.0.1:8000**

### Using OmniLens

1. Enter a reference news article URL.
2. Start the analysis.
3. Event Registry retrieves related articles.
4. FENICE extracts claims from the related articles.
5. Claude compares those claims against the reference article.
6. Review the results and available source evidence.

The initial startup may take longer because the FENICE model must be downloaded and loaded.

Press `Ctrl+C` in the terminal to stop the server.

## 7. API

OmniLens uses FastAPI.

The existing backend provides an article-analysis endpoint:

### `POST /api/analyze`

Example request:

```json
{
  "url": "https://example.com/news-article",
  "max_articles": 5
}
```

The response contains reference article metadata, related articles, extracted claims, and analysis results according to the active pipeline configuration.

Interactive API documentation is available at:

**http://127.0.0.1:8000/docs**

Additional endpoints and response fields should be documented after the final frontend integration.

## 8. Models and Technologies

| Component | Technology |
|---|---|
| News discovery | Event Registry (NewsAPI.ai) |
| Article preprocessing | Python |
| Claim extraction | FENICE / T5 |
| Claim classification | Claude Sonnet |
| Model inference | PyTorch, Hugging Face Transformers |
| Sentence tokenization | NLTK |
| Backend | FastAPI |
| Frontend | HTML, CSS, JavaScript (current prototype) |

### Model Evaluation

During development, the team evaluated multiple approaches for claim extraction and annotation.

**Claim extraction:** FENICE was selected after comparison with alternative extraction approaches, including OpenIE.

**Claim annotation:** The team evaluated pretrained NLI, DeBERTa-based models, fine-tuned ModernBERT, and Claude. Claude was selected for the application based on its evaluation results.

Research and evaluation artifacts are maintained separately from the application implementation.

## 9. Running Tests

From `backend/`, run:

```bash
python -m pytest tests/ -v
```

Individual tests can also be run:

```bash
python -m pytest tests/test_article_cleaner.py -v
python -m pytest tests/test_claim_cleaner.py -v
python -m pytest tests/test_claim_annotator.py -v
```

News discovery and model inference tests may require API credentials, internet access, or downloaded model weights.

## 10. Limitations

- Event Registry's available historical coverage depends on the API subscription.
- Some reference URLs may not be indexed by Event Registry.
- Retrieved article text may contain extraction artifacts or incomplete content.
- FENICE may occasionally generate incomplete or inaccurate claims.
- Claim classification depends on the available reference evidence and the model's interpretation.
- CONFLICTING claims are relatively rare in the annotated dataset, making reliable evaluation difficult.
- Cross-article disagreement does not establish which publisher is factually correct.

## 11. Development and Integration

The repository contains separate development branches for different components.

The `integration-final` branch is used to combine backend improvements, claim classification, and frontend functionality before merging into the default branch.

Changes should be tested locally before being merged into `master`.

### Contributing

```bash
git checkout integration-final
git pull
```

After making changes:

```bash
git add .
git commit -m "Describe your changes"
git push
```

Coordinate with the team before merging changes into the default branch.

---

**OmniLens — Cross-Article News Analysis**

Developed as an NLP research and application project.