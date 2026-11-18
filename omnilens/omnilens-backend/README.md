# OmniLens Backend

OmniLens is an NLP-powered news analysis application that discovers related news articles and extracts factual claims to help users compare how different sources report the same event.

The backend currently integrates **Event Registry** for news discovery and article retrieval, and **FENICE (T5-based claim extraction)** for extracting claims from related articles.

Claim annotation using Claude is planned as the next integration.

## 1. How It Works

The current pipeline follows these steps:

1. A user enters a reference news article URL through the web interface.
2. Event Registry identifies the article and its associated news event.
3. The application retrieves up to five related English-language articles.
4. Articles are filtered to reduce duplicate or syndicated content.
5. Article text is cleaned to remove common boilerplate and unrelated recommendations.
6. FENICE extracts factual claims from each related article.
7. Extracted claims are cleaned to remove obvious fragments, boilerplate, and duplicates within each article.
8. Results are displayed in the browser and can be downloaded as JSON.

**Current pipeline:**

`Reference URL → Event Registry → Article Filtering → Text Cleaning → FENICE → Claim Cleaning → JSON Output`

## 2. Project Structure

```text
omnilens-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI application
│   ├── news_provider.py       # Event Registry integration
│   ├── article_cleaner.py     # Article text preprocessing
│   ├── claim_extractor.py     # FENICE T5 claim extraction
│   ├── claim_cleaner.py       # Claim filtering and deduplication
│   ├── pipeline.py            # End-to-end orchestration
│   ├── index.html             # Local web interface
│   ├── claim_annotator.py     # Reserved for Claude integration
│   └── schemas.py             # Reserved for shared data schemas
├── tests/
│   ├── __init__.py
│   ├── test_news_provider.py
│   ├── test_claim_extractor.py
│   └── test_claim_cleaner.py
├── notebooks/                 # Research and evaluation notebooks
├── requirements.txt
├── requirements-lock.txt      # If generated
├── .env.example
├── .gitignore
└── README.md
```

## 3. Prerequisites

Before running the backend, make sure you have:

- Python 3.11
- Git
- An Event Registry API key
- An internet connection for news retrieval and initial model downloads

The FENICE model is downloaded automatically from Hugging Face on its first run.

## 4. Installation

### Step 1: Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd omnilens
```

To check out the backend development branch:

```bash
git switch ishika-backend
```

Navigate to the backend directory:

```bash
cd omnilens-backend
```

### Step 2: Create a virtual environment

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

Verify your Python version:

```bash
python --version
```

Expected version: Python 3.11.x.

### Step 3: Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Verify that the installed dependencies are compatible:

```bash
python -m pip check
```

If a tested `requirements-lock.txt` is available for your platform, you can use it instead for more reproducible installations.

### Step 4: Configure environment variables

Create a `.env` file inside `omnilens-backend`.

If `.env.example` exists:

```bash
cp .env.example .env
```

Add your Event Registry API key:

```env
EVENTREGISTRY_API_KEY=your_eventregistry_api_key
```

You can register for an API key at https://newsapi.ai/.

**Important:** Never commit `.env` or real API keys to GitHub. The `.gitignore` file should exclude them.

An Anthropic API key will be required once Claude claim annotation is integrated.

## 5. Running OmniLens

From the `omnilens-backend` directory, with the virtual environment activated, run:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open the application in your browser:

http://127.0.0.1:8000

### Using the application

1. Paste a news article URL into the input field.
2. Click **Analyze Article**.
3. Wait while Event Registry retrieves related articles and FENICE extracts their claims.
4. Review the extracted claims grouped by publisher.
5. Click **Download JSON** to save the results.

The first run may take longer because the FENICE model must be downloaded and loaded into memory.

Keep the terminal running while using the application. Press `Ctrl+C` to stop the server.

## 6. API Endpoint

The backend is built using FastAPI.

### `POST /api/analyze`

Accepts a reference article URL and returns the related articles with extracted claims.

**Example request:**

```json
{
  "url": "https://example.com/news-article",
  "max_articles": 5
}
```

`max_articles` supports values from 1 to 10 and defaults to 5.

**Example response (simplified):**

```json
{
  "pipeline_version": "1.1",
  "status": "extraction_complete",
  "event_id": "example_event_id",
  "reference_article": {
    "article_id": "ref_001",
    "title": "Reference Article",
    "url": "https://example.com/reference",
    "publisher": "Example Publisher",
    "published_at": "2026-11-12T14:00:00Z",
    "text": "Reference article text..."
  },
  "candidate_articles": [
    {
      "article_id": "cand_001",
      "title": "Related Article",
      "url": "https://example.com/related",
      "publisher": "Related Publisher",
      "text": "Related article text...",
      "extraction_status": "success",
      "claim_count": 1,
      "claims": [
        {
          "claim_id": "A001_C001",
          "article_id": "cand_001",
          "text": "An extracted factual claim.",
          "chunk_index": 0,
          "source_chunk": "Original source passage..."
        }
      ]
    }
  ],
  "summary": {
    "articles_found": 1,
    "articles_processed": 1,
    "total_claims": 1
  }
}
```

The actual response also contains publication metadata and claim-cleaning diagnostics.

Interactive API documentation is available at:

http://127.0.0.1:8000/docs

## 7. Models and Technologies

| Component | Technology | Purpose |
|---|---|---|
| Backend | FastAPI | REST API and application server |
| News discovery | Event Registry | Article search and event clustering |
| Article retrieval | Event Registry | Article text and metadata |
| Claim extraction | `Babelscape/t5-base-summarization-claim-extractor` | FENICE T5 claim extraction |
| Model inference | PyTorch / Transformers | Running claim extraction |
| Sentence splitting | NLTK | Preparing article chunks |
| Article deduplication | Python `difflib` | Filtering near-duplicate articles |
| Claim cleaning | Python regular expressions | Removing obvious invalid claims |
| Frontend | HTML, CSS, JavaScript | Local application interface |

FENICE runs on CUDA, Apple Silicon MPS, or CPU depending on the available hardware.

## 8. Running Tests

Run the claim-cleaning unit tests:

```bash
python -m pytest tests/test_claim_cleaner.py -v
```

Test Event Registry discovery:

```bash
python -m tests.test_news_provider
```

Test FENICE extraction:

```bash
python -m tests.test_claim_extractor
```

The Event Registry test requires a valid API key and available API quota.

The FENICE test downloads or loads the pretrained model and may take longer than the claim-cleaning tests.

To run all pytest-discoverable tests:

```bash
python -m pytest tests/ -v
```

Some integration tests may require external services and model downloads.

## 9. Current Limitations

- **Historical articles:** Event Registry's free testing access is limited. Older articles may require paid archive access.
- **Unindexed URLs:** The current pipeline requires the submitted reference article to be indexed by Event Registry.
- **Article completeness:** Retrieved text depends on Event Registry's coverage and extraction quality.
- **Claim quality:** FENICE may occasionally produce incomplete, redundant, or semantically incorrect claims. Rule-based cleaning removes obvious issues but does not guarantee factual faithfulness.
- **Duplicates:** Article deduplication is heuristic and may not identify every syndicated copy.
- **Language:** Related-article retrieval currently focuses on English-language news.
- **Annotation:** SHARED, NEW, and CONFLICTING classification has not yet been integrated.
- **Deployment:** The application is currently intended for local development and testing, not unrestricted public deployment.

## 10. Planned Improvements

- Integrate Claude-based claim annotation against the reference article.
- Return SHARED, NEW, and CONFLICTING labels with reference evidence and explanations.
- Improve unsupported-URL handling and fallback discovery.
- Test across multiple news events and publishers.
- Add stronger API security, request limits, and error handling.
- Improve the frontend and visualize cross-source comparisons.
- Prepare the backend for deployment.

## 11. Development Workflow

The backend implementation is maintained on the `ishika-backend` branch.

To contribute changes:

```bash
git switch ishika-backend
git pull
```

After making and testing changes:

```bash
git add .
git commit -m "Describe your changes"
git push
```

Coordinate with the team before merging backend changes into `main`.

---

**Project:** OmniLens  
**Current status:** News discovery, article retrieval, and claim extraction implemented. Claude claim annotation pending.