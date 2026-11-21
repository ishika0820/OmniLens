"""OmniLens API: staged comparison flow plus backward-compatible /api/analyze.

The reference and candidates stay server-side until a user chooses sources.
This prevents extracting/classifying unwanted articles (and unnecessary Claude calls).
Sessions and job progress live in memory: restarting the server clears them.
"""
import logging
import secrets
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from threading import Lock, Thread
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.news_provider import get_reference_article, get_candidates_for_reference
from app.pipeline import OmniLensPipeline

logger = logging.getLogger(__name__)
pipeline = None
analysis_lock = Lock()
store_lock = Lock()
sessions = OrderedDict()
jobs = OrderedDict()
SESSION_TTL = 45 * 60
MAX_SESSIONS = 30
MAX_JOBS = 40


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    pipeline = OmniLensPipeline()
    yield


app = FastAPI(title="OmniLens", description="Cross-article claim comparison", version="1.3.0", lifespan=lifespan)


class ArticleRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2048)
    # Optionally paste the source text, but discovery still requires the source URL.
    reference_text: str | None = Field(default=None, max_length=80000)


class DiscoverRequest(BaseModel):
    discovery_id: str = Field(min_length=12, max_length=128)
    max_articles: int = Field(default=5, ge=1, le=10)


class CompareRequest(BaseModel):
    discovery_id: str = Field(min_length=12, max_length=128)
    article_ids: list[str] = Field(min_length=1, max_length=10)


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2048)
    max_articles: int = Field(default=5, ge=1, le=10)


def check_url(url):
    parsed = urlparse(url)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password):
        raise HTTPException(status_code=400, detail="Enter a valid public article URL.")


def public_article(article, include_excerpt=False):
    data = {key: article.get(key) for key in
            ("article_id", "url", "title", "publisher", "published_at")}
    if include_excerpt:
        data["excerpt"] = " ".join((article.get("text") or "").split())[:700]
    return data


def cleanup(now=None):
    now = time.monotonic() if now is None else now
    for key in list(sessions):
        if sessions[key]["expires"] < now:
            del sessions[key]
    for key in list(jobs):
        if jobs[key]["expires"] < now and jobs[key]["status"] not in ("queued", "running"):
            del jobs[key]
    while len(sessions) > MAX_SESSIONS:
        sessions.popitem(last=False)
    for key in list(jobs):
        if len(jobs) <= MAX_JOBS:
            break
        if jobs[key]["status"] not in ("queued", "running"):
            del jobs[key]


def require_session(token, candidates=False):
    with store_lock:
        cleanup()
        session = sessions.get(token)
        if session is None:
            raise HTTPException(status_code=404, detail="This comparison session expired. Start a new analysis.")
        if candidates and session.get("news_data") is None:
            raise HTTPException(status_code=409, detail="Discover related articles first.")
        sessions.move_to_end(token)
        return session


def translate_error(exc):
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    logger.exception("OmniLens pipeline failed")
    raise HTTPException(status_code=502, detail="Analysis failed. Check the server logs and API credentials.") from exc


@app.post("/api/reference")
async def reference_article(request: ArticleRequest):
    """Step 1 → 2: Resolve the story and let the user confirm it."""
    check_url(request.url)
    try:
        info = await run_in_threadpool(get_reference_article, request.url)
        if request.reference_text is not None:
            text = request.reference_text.strip()
            if len(text) < 100:
                raise ValueError("Pasted article text must contain at least 100 characters.")
            info["reference_article"] = {**info["reference_article"], "text": text}
    except Exception as exc:
        translate_error(exc)
    token = secrets.token_urlsafe(24)
    with store_lock:
        cleanup()
        sessions[token] = {"expires": time.monotonic() + SESSION_TTL,
                           "reference_data": info, "news_data": None, "completed": {}}
    return {"discovery_id": token, "reference_article": public_article(info["reference_article"], True),
            "expires_in_seconds": SESSION_TTL}


@app.post("/api/discover")
async def discover_related(request: DiscoverRequest):
    """Step 3: List related articles only; no FENICE or Claude yet."""
    session = require_session(request.discovery_id)
    try:
        data = await run_in_threadpool(get_candidates_for_reference, session["reference_data"], request.max_articles)
    except Exception as exc:
        translate_error(exc)
    if not data["candidate_articles"]:
        raise HTTPException(status_code=422, detail="No related articles with usable text were found.")
    with store_lock:
        if request.discovery_id not in sessions:
            raise HTTPException(status_code=404, detail="Session expired. Start again.")
        sessions[request.discovery_id]["news_data"] = data
    return {"discovery_id": request.discovery_id, "event_id": data["event_id"],
            "reference_article": public_article(data["reference_article"], True),
            "candidate_articles": [public_article(a, True) for a in data["candidate_articles"]],
            "articles_found": len(data["candidate_articles"])}


def selected_data(request):
    session = require_session(request.discovery_id, candidates=True)
    data = session["news_data"]
    allowed = {a["article_id"] for a in data["candidate_articles"]}
    if len(set(request.article_ids)) != len(request.article_ids):
        raise HTTPException(status_code=422, detail="Remove duplicate article selections.")
    if not set(request.article_ids).issubset(allowed):
        raise HTTPException(status_code=422, detail="One or more selected articles were not discovered in this session.")
    # Preserve discovery order so article and claim IDs remain deterministic.
    selected = [a["article_id"] for a in data["candidate_articles"] if a["article_id"] in request.article_ids]
    return data, selected


def run_comparison(data, selected, progress=None):
    with analysis_lock:
        return pipeline.analyze_selected(data, selected, progress=progress)


@app.post("/api/compare")
async def compare_selected(request: CompareRequest):
    """Synchronous alternative for API users; compares selected articles only."""
    data, selected = selected_data(request)
    try:
        return await run_in_threadpool(run_comparison, data, selected)
    except Exception as exc:
        translate_error(exc)


def job_summary(job):
    summary = {k: job[k] for k in ("job_id", "status", "stage", "message", "processed", "total")}
    if job["status"] == "completed":
        summary["result"] = job["result"]
    if job["status"] == "failed":
        summary["error"] = job["error"]
    return summary


def execute_job(job_id, data, selected, discovery_id, key):
    def progress(stage, message, processed, total):
        with store_lock:
            jobs[job_id].update(status="running", stage=stage, message=message,
                                processed=processed, total=total)
    try:
        progress("preparing", "Preparing selected articles", 0, len(selected))
        result = run_comparison(data, selected, progress=progress)
        with store_lock:
            jobs[job_id].update(status="completed", stage="complete", message="Comparison complete",
                                result=result, processed=len(selected), total=len(selected))
            session = sessions.get(discovery_id)
            if session is not None:
                session["completed"][key] = job_id
    except Exception:
        logger.exception("Selected comparison failed")
        with store_lock:
            jobs[job_id].update(status="failed", stage="error", message="Comparison failed",
                                error="The comparison failed. Check the server logs and API keys.")


@app.post("/api/compare/start")
async def start_selected_comparison(request: CompareRequest):
    """Step 4: Start a job with observable, real processing stages."""
    data, selected = selected_data(request)
    key = tuple(selected)
    with store_lock:
        cleanup()
        for existing in jobs.values():
            if (existing.get("discovery_id") == request.discovery_id
                    and existing.get("selection") == key
                    and existing["status"] in ("queued", "running", "completed")):
                return job_summary(existing)
        job_id = secrets.token_urlsafe(24)
        jobs[job_id] = {"job_id": job_id, "status": "queued", "stage": "queued",
                        "message": "Waiting to process selected articles", "processed": 0,
                        "total": len(selected), "expires": time.monotonic() + 2 * SESSION_TTL,
                        "discovery_id": request.discovery_id, "selection": key}
    Thread(target=execute_job, args=(job_id, data, selected, request.discovery_id, key), daemon=True).start()
    return job_summary(jobs[job_id])


@app.get("/api/compare/status/{job_id}")
async def comparison_status(job_id: str):
    with store_lock:
        cleanup()
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Comparison job unavailable or expired.")
        return job_summary(job)


@app.post("/api/analyze")
async def analyze_article(request: AnalyzeRequest):
    """Legacy all-in-one endpoint, retained for existing clients."""
    check_url(request.url)
    try:
        def legacy():
            with analysis_lock:
                return pipeline.analyze(request.url, request.max_articles)
        return await run_in_threadpool(legacy)
    except Exception as exc:
        translate_error(exc)


@app.get("/", response_class=HTMLResponse)
def homepage():
    from pathlib import Path
    return (Path(__file__).resolve().parent / "index.html").read_text(encoding="utf-8")
