from contextlib import asynccontextmanager
from threading import Lock
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.pipeline import OmniLensPipeline


pipeline = None
analysis_lock = Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    pipeline = OmniLensPipeline()
    yield


app = FastAPI(
    title="OmniLens",
    description="Cross-article claim extraction",
    version="1.0.0",
    lifespan=lifespan
)


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2048)
    max_articles: int = Field(default=5, ge=1, le=10)


def run_analysis(url, max_articles):
    # Avoid simultaneous inference on the same model.
    with analysis_lock:
        return pipeline.analyze(url, max_articles)


@app.post("/api/analyze")
async def analyze_article(request: AnalyzeRequest):
    parsed = urlparse(request.url)

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid public article URL."
        )

    try:
        return await run_in_threadpool(
            run_analysis,
            request.url,
            request.max_articles
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Article analysis failed. Check the server logs."
        )


@app.get("/", response_class=HTMLResponse)
def homepage():
    with open("app/index.html", encoding="utf-8") as file:
        return file.read()