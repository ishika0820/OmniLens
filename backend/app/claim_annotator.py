"""Label each candidate claim as SHARED, NEW or CONFLICTING against the reference article.

Ported from Models/claude_claim_classification/classify_claims.py. The prompt,
the 20 few-shot examples and the output schema are unchanged, and the default
settings match the best validation run (claude-sonnet-5-5, effort "medium",
20 examples, macro-F1 0.917 on the 212 validation claims).

Each claim is sent in its own request together with the full reference article.
The instructions and the reference article are both cached, so every claim
after the first one costs much less.
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_FILE = PROMPT_DIR / "classification_prompt.txt"
EXAMPLES_FILE = PROMPT_DIR / "few_shot_examples_train_20ex.json"

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_EFFORT = "medium"
DEFAULT_WORKERS = 6
MAX_TOKENS = 16000
LABELS = ["SHARED", "NEW", "CONFLICTING"]

# If these models decline a request, the API re-runs it on a fallback model
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Structured output: the explanation comes before the label so the model reasons first
LABEL_SCHEMA = {
    "type": "object",
    "properties": {
        "reference_evidence": {"type": "string"},
        "explanation": {"type": "string"},
        "label": {"type": "string", "enum": LABELS},
        "confidence": {"type": "string", "enum": ["High", "Medium", "Low"]},
    },
    "required": ["reference_evidence", "explanation", "label", "confidence"],
    "additionalProperties": False,
}


class LabelError(Exception):
    """The model answered, but the answer has no usable label."""


# ---------- prompt ----------

def format_example(example):
    lines = [f"Candidate claim: {example['claim']}"]
    if example["label"] == "NEW":
        lines.append("Reference says: nothing about this specific fact.")
    else:
        lines.append(f"Reference says: {example['reference_evidence']}")
    lines.append(f"Label: {example['label']}")
    if example.get("notes"):
        lines.append(f"Annotator note: {example['notes']}")
    return "<example>\n" + "\n".join(lines) + "\n</example>"


def build_system_prompt(examples):
    """The instructions with the few-shot examples filled in."""
    rendered = "\n\n".join(format_example(e) for e in examples)
    # .replace instead of .format, because the prompt may contain other braces
    return PROMPT_FILE.read_text(encoding="utf-8").replace("{few_shot_examples}", rendered)


def build_user_content(reference, claim_text):
    reference_block = (f'<reference_article title="{reference.get("title") or ""}" '
                       f'source="{reference.get("publisher") or ""}">\n'
                       f'{reference["text"]}\n</reference_article>')
    return [
        # Cached: every claim of the same analysis sends the same reference text
        {"type": "text", "text": reference_block, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": f"<candidate_claim>{claim_text}</candidate_claim>\n\n"
                                 "Label this candidate claim against the reference article."},
    ]


# ---------- API ----------

def call_claude(client, model, effort, system_prompt, user_content):
    extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"} if model in FALLBACK_MODELS else {}
    with client.beta.messages.stream(
        model=model,
        max_tokens=MAX_TOKENS,
        # Cached: the instructions and few-shot examples are the same in every request
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_content}],
        output_config={
            "effort": effort,
            "format": {"type": "json_schema", "schema": LABEL_SCHEMA},
        },
        **extra,
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        category = getattr(response.stop_details, "category", None)
        raise LabelError(f"refused by the API's safety check (category: {category})")
    texts = [block.text for block in response.content if block.type == "text"]
    if response.stop_reason == "max_tokens" or not texts:
        raise LabelError(f"stop_reason={response.stop_reason}")
    answer = json.loads(texts[-1])
    if answer.get("label") not in LABELS:
        raise LabelError(f"unexpected label {answer.get('label')!r}")
    return answer


# ---------- annotator ----------

class ClaudeClaimAnnotator:
    """Labels FENICE claims against the reference article.

    annotate() adds these keys to every claim dict (in place) and returns the list:
        label               "SHARED" | "NEW" | "CONFLICTING", or None if labeling failed
        confidence          "High" | "Medium" | "Low", or None
        reference_evidence  the matching reference sentence ("" for NEW)
        explanation         one or two sentences on why
        annotation_error    "" on success, otherwise the error message
    """

    def __init__(self, model=None, effort=None, workers=None, client=None,
                 examples_file=EXAMPLES_FILE):
        self.model = model or os.getenv("OMNILENS_CLAUDE_MODEL", DEFAULT_MODEL)
        self.effort = effort or os.getenv("OMNILENS_CLAUDE_EFFORT", DEFAULT_EFFORT)
        self.workers = workers or int(os.getenv("OMNILENS_CLAUDE_WORKERS", DEFAULT_WORKERS))

        examples = json.loads(Path(examples_file).read_text(encoding="utf-8"))
        self.system_prompt = build_system_prompt(examples)

        if client is None:
            api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY missing from .env")
            workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip().strip('"')
            headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
            client = anthropic.Anthropic(api_key=api_key, default_headers=headers, max_retries=5)
        self.client = client

    def _label_one(self, reference, claim):
        """The fields to add to one claim."""
        result = {"label": None, "confidence": None, "reference_evidence": "",
                  "explanation": "", "annotation_error": ""}
        try:
            answer = call_claude(self.client, self.model, self.effort, self.system_prompt,
                                 build_user_content(reference, claim["text"]))
            result.update({key: answer[key] for key in
                           ("label", "confidence", "reference_evidence", "explanation")})
        except LabelError as e:
            result["annotation_error"] = f"LabelError: {e}"
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError,
                anthropic.NotFoundError):
            raise  # wrong key, workspace or model name: fail the whole analysis
        except (anthropic.APIStatusError, anthropic.APIConnectionError,
                json.JSONDecodeError) as e:
            result["annotation_error"] = f"{type(e).__name__}: {e}"
        return result

    def annotate(self, reference, claims):
        """Label every claim against reference ({title, publisher, text})."""
        if not claims:
            return claims
        start = time.perf_counter()

        # The first request alone writes the cache for the instructions and the
        # reference; the others then read it instead of each writing it again.
        claims[0].update(self._label_one(reference, claims[0]))
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            results = pool.map(lambda c: self._label_one(reference, c), claims[1:])
            for claim, result in zip(claims[1:], results):
                claim.update(result)

        failed = sum(1 for c in claims if c["label"] is None)
        print(f"Labeled {len(claims) - failed}/{len(claims)} claims with {self.model}"
              f" (effort {self.effort}) in {time.perf_counter() - start:.0f}s", flush=True)
        return claims
