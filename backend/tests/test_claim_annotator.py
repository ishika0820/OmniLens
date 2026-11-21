import json
from types import SimpleNamespace

import app.pipeline as pipeline_module
from app.claim_annotator import ClaudeClaimAnnotator
from app.pipeline import OmniLensPipeline

REFERENCE = {
    "article_id": "R1",
    "url": "https://example.com/reference",
    "title": "Storm cuts power",
    "publisher": "Daily Journal",
    "published_at": "2026-11-12T10:30:00Z",
    "text": ("A storm cut power to 40,000 homes on Tuesday. "
             "Officials said full restoration is not expected before Saturday morning."),
}

# The answer the fake Claude gives for each claim text
ANSWERS = {
    "Power was cut to 40,000 homes.": {
        "reference_evidence": "A storm cut power to 40,000 homes on Tuesday.",
        "explanation": "Same number of homes.", "label": "SHARED", "confidence": "High"},
    "Full service will return by Thursday evening.": {
        "reference_evidence": "full restoration is not expected before Saturday morning",
        "explanation": "Thursday vs Saturday.", "label": "CONFLICTING", "confidence": "Medium"},
    "An independent engineering review was ordered.": {
        "reference_evidence": "", "explanation": "The reference does not mention a review.",
        "label": "NEW", "confidence": "Low"},
}


class FakeStream:
    def __init__(self, answer):
        self.answer = answer

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        if self.answer is None:
            return SimpleNamespace(content=[], stop_reason="max_tokens")
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(self.answer))],
            stop_reason="end_turn")


class FakeClient:
    def __init__(self):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self.stream))

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        claim_text = kwargs["messages"][0]["content"][1]["text"]
        for claim, answer in ANSWERS.items():
            if claim in claim_text:
                return FakeStream(answer)
        return FakeStream(None)  # unknown claim -> the model "fails"


def make_claims():
    return [{"claim_id": f"A001_C{i:03d}", "text": text}
            for i, text in enumerate([*ANSWERS, "Something the fake model cannot label."], 1)]


def test_annotator_labels_claims_and_records_failures():
    client = FakeClient()
    claims = ClaudeClaimAnnotator(client=client, workers=2).annotate(REFERENCE, make_claims())

    assert [c["label"] for c in claims] == ["SHARED", "CONFLICTING", "NEW", None]
    assert claims[3]["annotation_error"].startswith("LabelError")
    assert claims[0]["annotation_error"] == ""
    assert set(claims[0]) == {"claim_id", "text", "label", "confidence",
                              "reference_evidence", "explanation", "annotation_error"}
    # The prompt has the 20 few-shot examples and uses the validated settings
    first = client.calls[0]
    assert first["system"][0]["text"].count("<example>") == 20
    assert first["output_config"]["effort"] == "medium"
    assert first["model"] == "claude-sonnet-5-5"


def fake_related_articles(url, max_articles=5):
    return {
        "event_id": "eng-123",
        "reference_article": REFERENCE,
        "candidate_articles": [{
            "article_id": "A1", "url": "https://example.com/a1", "title": "Restoration timeline",
            "publisher": "Reuters", "published_at": "2026-11-13T08:00:00Z",
            "text": "Unused because the fake extractor ignores it.",
        }],
    }


class FakeExtractor:
    def extract_claims(self, text):
        return make_claims()


def test_pipeline_adds_labels_to_claims(monkeypatch):
    monkeypatch.setattr(pipeline_module, "get_related_articles", fake_related_articles)
    pipeline = OmniLensPipeline(extractor=FakeExtractor(),
                                annotator=ClaudeClaimAnnotator(client=FakeClient(), workers=2))

    result = pipeline.analyze(REFERENCE["url"])

    assert result["status"] == "annotation_complete"
    claims = result["candidate_articles"][0]["claims"]
    assert [c["label"] for c in claims] == ["SHARED", "CONFLICTING", "NEW", None]
    assert result["summary"]["label_counts"] == {"SHARED": 1, "NEW": 1, "CONFLICTING": 1}
    assert result["summary"]["labeled_claims"] == 3
    assert result["summary"]["failed_labels"] == 1
