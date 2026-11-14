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

def get_related_articles(reference_url: str, max_articles: int = 5):
    """
    Retrieve the reference article and related articles
    from the same Event Registry event cluster.
    """

    api_key = os.getenv("EVENTREGISTRY_API_KEY")

    if not api_key:
        raise RuntimeError(
            "EVENTREGISTRY_API_KEY missing from .env"
        )

    er = EventRegistry(
        apiKey=api_key,
        allowUseOfArchive=False
    )

    # Find reference article
    mapper = ArticleMapper(er)
    article_uri = mapper.getArticleUri(reference_url)

    if not article_uri:
        raise ValueError(
            "Reference article not found in Event Registry."
        )

    if isinstance(article_uri, list):
        article_uri = article_uri[0]

    # Retrieve reference article information
    query = QueryArticle(article_uri)

    query.setRequestedResult(
        RequestArticleInfo(
            returnInfo=ReturnInfo(
                articleInfo=ArticleInfoFlags(bodyLen=-1)
            )
        )
    )

    result = er.execQuery(query)

    reference_info = result.get(
        article_uri, {}
    ).get("info", {})

    event_id = reference_info.get("eventUri")

    if not event_id:
        raise ValueError(
            "No event cluster found for this article."
        )

    # Retrieve related English-language articles
    event_query = QueryEventArticlesIter(
        event_id,
        lang="eng"
    )

    related = list(
        event_query.execQuery(
            er,
            sortBy="cosSim",
            maxItems=30,
            returnInfo=ReturnInfo(
                articleInfo=ArticleInfoFlags(bodyLen=-1)
            )
        )
    )

    reference_domain = urlparse(reference_url).netloc

    selected = []
    seen_domains = set()

    for article in related:

        url = article.get("url")
        text = article.get("body") or ""

        if not url or len(text.strip()) < 500:
            continue

        if (
            article.get("uri") == article_uri
            or url.rstrip("/") == reference_url.rstrip("/")
        ):
            continue

        domain = urlparse(url).netloc.lower()

        if domain == reference_domain:
            continue

        if domain in seen_domains:
            continue

        if is_duplicate_article(text, selected):
            print(
                f"Skipping near-duplicate article: "
                f"{article.get('title')}"
            )
            continue

        seen_domains.add(domain)

        selected.append({
            "article_id": str(article.get("uri")),
            "url": url,
            "title": article.get("title"),
            "publisher": (
                article.get("source") or {}
            ).get("title"),
            "published_at": article.get("dateTime"),
            "text": text
        })

        if len(selected) >= max_articles:
            break

    reference = {
        "article_id": str(article_uri),
        "url": reference_url,
        "title": reference_info.get("title"),
        "publisher": (
            reference_info.get("source") or {}
        ).get("title"),
        "published_at": reference_info.get("dateTime"),
        "text": reference_info.get("body") or ""
    }

    return {
        "event_id": event_id,
        "reference_article": reference,
        "candidate_articles": selected
    }