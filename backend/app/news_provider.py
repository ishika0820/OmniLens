import re
from difflib import SequenceMatcher
import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from eventregistry import (
    EventRegistry,
    ArticleMapper,
    QueryArticle,
    RequestArticleInfo,
    QueryEventArticlesIter,
    ReturnInfo,
    ArticleInfoFlags
)

load_dotenv()


def normalize_article_text(text):
    """Normalize text for duplicate comparison."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_duplicate_article(
    new_text,
    selected_articles,
    threshold=0.85
):
    """
    Detect near-identical article bodies.
    Returns True if the new article substantially
    duplicates an already selected article.
    """
    normalized_new = normalize_article_text(new_text)

    for article in selected_articles:
        normalized_existing = normalize_article_text(
            article["text"]
        )

        similarity = SequenceMatcher(
            None,
            normalized_new,
            normalized_existing,
            autojunk=False
        ).ratio()

        if similarity >= threshold:
            return True

    return False

def _event_registry():
    api_key = os.getenv("EVENTREGISTRY_API_KEY")
    if not api_key:
        raise RuntimeError("EVENTREGISTRY_API_KEY missing from .env")
    return EventRegistry(apiKey=api_key, allowUseOfArchive=False)


def get_reference_article(reference_url: str):
    """Resolve the starting story without processing any candidate articles."""
    er = _event_registry()
    mapper = ArticleMapper(er)
    article_uri = mapper.getArticleUri(reference_url)
    if not article_uri:
        raise ValueError("Reference article not found in Event Registry.")
    if isinstance(article_uri, list):
        article_uri = article_uri[0]

    query = QueryArticle(article_uri)
    query.setRequestedResult(RequestArticleInfo(
        returnInfo=ReturnInfo(articleInfo=ArticleInfoFlags(bodyLen=-1))
    ))
    result = er.execQuery(query)
    info = result.get(article_uri, {}).get("info", {})
    event_id = info.get("eventUri")
    if not event_id:
        raise ValueError("No event cluster found for this article.")
    reference = {
        "article_id": str(article_uri),
        "url": reference_url,
        "title": info.get("title"),
        "publisher": (info.get("source") or {}).get("title"),
        "published_at": info.get("dateTime"),
        "text": info.get("body") or ""
    }
    if not reference["text"].strip():
        raise ValueError("Reference article has no usable text.")
    return {"event_id": event_id, "reference_article": reference}


def get_candidates_for_reference(reference_data, max_articles: int = 5):
    """Fetch event matches only after the user confirms the reference."""
    er = _event_registry()
    event_query = QueryEventArticlesIter(reference_data["event_id"], lang="eng")
    related = event_query.execQuery(
        er, sortBy="cosSim", maxItems=30,
        returnInfo=ReturnInfo(articleInfo=ArticleInfoFlags(bodyLen=-1))
    )
    reference = reference_data["reference_article"]
    reference_domain = urlparse(reference["url"]).netloc.lower()
    selected, seen_domains = [], set()
    for article in related:
        url, text = article.get("url"), article.get("body") or ""
        if not url or len(text.strip()) < 500:
            continue
        if (str(article.get("uri")) == reference["article_id"]
                or url.rstrip("/") == reference["url"].rstrip("/")):
            continue
        domain = urlparse(url).netloc.lower()
        if domain == reference_domain or domain in seen_domains:
            continue
        if is_duplicate_article(text, selected):
            continue
        seen_domains.add(domain)
        selected.append({
            "article_id": str(article.get("uri")),
            "url": url,
            "title": article.get("title"),
            "publisher": (article.get("source") or {}).get("title"),
            "published_at": article.get("dateTime"),
            "text": text,
        })
        if len(selected) >= max_articles:
            break
    return {**reference_data, "candidate_articles": selected}


def get_related_articles(reference_url: str, max_articles: int = 5):
    """Legacy single-step API remains compatible with existing clients."""
    ref = get_reference_article(reference_url)
    return get_candidates_for_reference(ref, max_articles)
