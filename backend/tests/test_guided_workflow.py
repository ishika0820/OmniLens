"""Staged UI API contract tests with fake news and AI backends (no keys required)."""
import time
import pytest
from fastapi.testclient import TestClient
from app import main

REF = {"article_id": "ref", "url": "https://example.com/news",
       "title": "Example Story", "publisher": "Example Daily", "text": "Report text. " * 50}
ARTICLES = [{"article_id": key, "title": "Related " + key,
             "url": f"https://other.example/{key}", "publisher": "News", "text": "Content " * 100}
            for key in ("a", "b", "c")]


class FakePipeline:
    def __init__(self):
        self.calls = []

    def analyze_selected(self, data, selected, progress=None):
        self.calls.append(selected)
        if progress:
            progress("extracting", "Extracting", 1, len(selected))
            progress("classifying", "Classifying", 0, len(selected))
            progress("organizing", "Organizing", len(selected), len(selected))
        return {"reference_article": data["reference_article"],
                "candidate_articles": [a for a in data["candidate_articles"] if a["article_id"] in selected],
                "summary": {"total_claims": 0}}

    def analyze(self, url, max_articles):
        return {"legacy": url, "max_articles": max_articles}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "OmniLensPipeline", FakePipeline)
    monkeypatch.setattr(main, "get_reference_article", lambda url: {
        "event_id": "evt", "reference_article": {**REF, "url": url}
    })
    monkeypatch.setattr(main, "get_candidates_for_reference", lambda ref, max_articles: {
        **ref, "candidate_articles": ARTICLES[:max_articles]
    })
    with TestClient(main.app) as session:
        yield session


def test_selected_only_and_legacy(client):
    first = client.post("/api/reference", json={"url": REF["url"]})
    assert first.status_code == 200
    token = first.json()["discovery_id"]
    assert "text" not in first.json()["reference_article"]

    discovered = client.post("/api/discover", json={"discovery_id": token, "max_articles": 3})
    assert discovered.status_code == 200
    assert len(discovered.json()["candidate_articles"]) == 3
    assert "text" not in discovered.json()["candidate_articles"][0]
    assert main.pipeline.calls == []

    started = client.post("/api/compare/start", json={"discovery_id": token,
                                                       "article_ids": ["c", "a"]})
    assert started.status_code == 200
    job = started.json()["job_id"]
    for _ in range(100):
        status = client.get(f"/api/compare/status/{job}")
        if status.json()["status"] == "completed":
            break
        time.sleep(.02)
    assert status.json()["status"] == "completed"
    assert [a["article_id"] for a in status.json()["result"]["candidate_articles"]] == ["a", "c"]
    assert main.pipeline.calls == [["a", "c"]]
    assert client.post("/api/compare/start", json={"discovery_id": token,
                   "article_ids": ["a", "c"]}).json()["job_id"] == job
    assert client.post("/api/compare/start", json={"discovery_id": token,
                   "article_ids": ["unknown"]}).status_code == 422
    assert client.post("/api/compare/start", json={"discovery_id": token,
                   "article_ids": ["a", "a"]}).status_code == 422
    assert client.post("/api/analyze", json={"url": REF["url"],
                                                      "max_articles": 2}).json()["max_articles"] == 2
