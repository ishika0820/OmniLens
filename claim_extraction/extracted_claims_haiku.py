"""Extract claims from every article in validationdataset.csv with Claude Haiku 5.5.

Each article is sent whole, in one request, as its passages labeled with their
IDs ([6.1_p001], [6.1_p002], ...). Haiku returns every claim together with the
ID of the passage that states it. The prompt is extraction_prompt.txt in this
folder; it asks for claims that are atomic, faithful, not redundant and keep
their entities.

Source URLs come from validation_articles.csv, the "Validation Dataset" sheet of
diverse_summ_annotation_workbook.xlsx (the 5 candidate articles of each event).

The API key is read from .env in this folder (copy .env.example to .env).
Use a key created inside a workspace; if the key is not scoped to one, also set
ANTHROPIC_WORKSPACE_ID.

Run from this folder:
    python extract_claims_haiku.py                  # every article
    python extract_claims_haiku.py --limit 2        # try 2 articles first
    python extract_claims_haiku.py --articles 6.1 13.10
    python extract_claims_haiku.py --redo           # extract again even if already done

Re-running skips articles already extracted with the same prompt, model and
effort, so an interrupted run can be resumed without paying twice.

Outputs (in this folder):
    haiku_claims.csv        one row per claim: event_id, article_id, passage_id,
                            claim_id, claim, passage_text, source_url
    haiku_cost_summary.csv  one row per article plus a TOTAL row
    haiku_run_log.jsonl     one line per request: tokens, cost, time, raw answer, errors
"""

import argparse
import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv

FOLDER = Path(__file__).resolve().parent
PROMPT_FILE = FOLDER / "extraction_prompt.txt"
VALIDATION_FILE = FOLDER / "validationdataset.csv"
ARTICLES_FILE = FOLDER / "validation_articles.csv"
CLAIMS_FILE = FOLDER / "haiku_claims.csv"
RUN_LOG = FOLDER / "haiku_run_log.jsonl"
COST_SUMMARY = FOLDER / "haiku_cost_summary.csv"

# override=True so the key in this folder's .env wins over any key set elsewhere
load_dotenv(FOLDER / ".env", override=True)

MODEL = "claude-haiku-5-5"
# A long article can have hundreds of claims, so answers are streamed
MAX_TOKENS = 64000
# Claude Haiku 5.5 prices in USD per million tokens, for prompts up to 100K tokens
PRICE_INPUT, PRICE_OUTPUT = 0.10, 0.50

CLAIM_COLUMNS = ["event_id", "article_id", "passage_id", "claim_id", "claim", "passage_text", "source_url"]


def claims_schema(passage_ids):
    """Structured outputs force JSON in this shape, with passage IDs limited to this article's."""
    return {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "passage_id": {"type": "string", "enum": passage_ids},
                        "claim": {"type": "string"},
                    },
                    "required": ["passage_id", "claim"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["claims"],
        "additionalProperties": False,
    }


def load_prompt():
    """Split the prompt file into the fixed system part and the per-article template."""
    text = PROMPT_FILE.read_text()
    system_prompt, template = text.split("NOW EXTRACT", 1)
    return system_prompt.strip(), "NOW EXTRACT" + template


def load_articles():
    """Group the passages into articles, in the order articles appear in the file."""
    # Read everything as text so IDs like "13.10" do not become the number 13.1
    passages = pd.read_csv(VALIDATION_FILE, dtype=str, keep_default_na=False)
    urls = pd.read_csv(ARTICLES_FILE, dtype=str, keep_default_na=False)
    urls = dict(zip(urls["article_id"], urls["source_url"]))

    articles = []
    for article_id, rows in passages.groupby("article_id", sort=False):
        rows = rows.sort_values("passage_id")  # p001, p002, ... are zero-padded
        articles.append({
            "event_id": rows["event_id"].iloc[0],
            "article_id": article_id,
            "source_url": urls.get(article_id, ""),
            "passages": dict(zip(rows["passage_id"], rows["passage_text"])),
        })
    return articles


def extract(client, system_prompt, template, article, effort):
    """One request for one article; returns a log record with the claims or the error."""
    passage_ids = list(article["passages"])
    article_text = "\n".join(f"[{pid}] {text}" for pid, text in article["passages"].items())
    record = {
        "article_id": article["article_id"],
        "article_words": sum(len(text.split()) for text in article["passages"].values()),
        "claims": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "seconds": 0.0,
        "error": None,
        "raw_answer": None,
    }
    # .replace instead of .format, because the prompt contains literal JSON braces
    user_text = template.replace("{article_text}", article_text)
    start = time.perf_counter()
    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
            output_config={
                "effort": effort,
                "format": {"type": "json_schema", "schema": claims_schema(passage_ids)},
            },
        ) as stream:
            response = stream.get_final_message()
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError,
            anthropic.NotFoundError, anthropic.BadRequestError):
        raise  # wrong key, missing workspace or bad request: every article would fail the same way
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
        # The SDK already retried rate limits and server errors; re-run later to resume
        record["error"] = f"API error: {e}"
        record["seconds"] = round(time.perf_counter() - start, 2)
        return record

    usage = response.usage
    # output_tokens includes the model's thinking, which is billed as output
    record.update(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=(usage.input_tokens * PRICE_INPUT + usage.output_tokens * PRICE_OUTPUT) / 1_000_000,
        seconds=round(time.perf_counter() - start, 2),
    )
    texts = [block.text for block in response.content if block.type == "text"]
    if response.stop_reason == "refusal":
        category = getattr(response.stop_details, "category", None)
        record["error"] = f"refused by the API's safety check (category: {category})"
    elif response.stop_reason == "max_tokens" or not texts:
        record["error"] = f"stop_reason={response.stop_reason}"
    else:
        record["raw_answer"] = texts[-1]
        record["claims"] = [{"passage_id": c["passage_id"], "claim": c["claim"].strip()}
                            for c in json.loads(texts[-1])["claims"] if c["claim"].strip()]
    return record


def load_run_log():
    """Earlier requests, one per line; the last line for each article and setup wins."""
    records = {}
    if RUN_LOG.exists():
        with open(RUN_LOG) as f:
            for line in f:
                record = json.loads(line)
                records[(record["article_id"], record["setup_hash"])] = record
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"],
                        help="how much Haiku thinks before answering (more = more output tokens)")
    parser.add_argument("--articles", nargs="+", help="only these article IDs, e.g. 6.1 13.10")
    parser.add_argument("--limit", type=int, help="extract only this many new articles (for a trial run)")
    parser.add_argument("--redo", action="store_true", help="extract again even if already done")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(f"Set ANTHROPIC_API_KEY in {FOLDER / '.env'} (copy .env.example to .env).")
    # A key created inside a workspace needs no header; an unscoped key must name its workspace
    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()
    headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
    client = anthropic.Anthropic(api_key=api_key, default_headers=headers, max_retries=5)

    system_prompt, template = load_prompt()
    # Results made with a different prompt, model or effort are extracted again
    setup_hash = hashlib.sha256(
        json.dumps([MODEL, args.effort, system_prompt, template, claims_schema(["ID"])]).encode()
    ).hexdigest()[:8]

    articles = load_articles()
    missing_urls = [a["article_id"] for a in articles if not a["source_url"]]
    if missing_urls:
        print(f"No source URL in {ARTICLES_FILE.name} for: {', '.join(missing_urls)}")
    if args.articles:
        articles = [a for a in articles if a["article_id"] in args.articles]
    records = load_run_log()

    def is_done(article):
        record = records.get((article["article_id"], setup_hash))
        return record is not None and record["error"] is None

    pending = [a for a in articles if args.redo or not is_done(a)]
    if args.limit:
        pending = pending[:args.limit]
    print(f"{len(articles)} articles, {len(articles) - len(pending)} already done with this setup, "
          f"extracting {len(pending)} now with {MODEL} (effort {args.effort}, setup {setup_hash})\n")

    with open(RUN_LOG, "a") as f:
        for number, article in enumerate(pending, 1):
            record = extract(client, system_prompt, template, article, args.effort)
            record.update(setup_hash=setup_hash, model=MODEL, effort=args.effort,
                          timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            records[(article["article_id"], setup_hash)] = record
            f.write(json.dumps(record) + "\n")
            f.flush()
            status = record["error"] or f"{len(record['claims'])} claims"
            print(f"[{number}/{len(pending)}] {article['article_id']} ({record['article_words']} words): "
                  f"{status}, {record['input_tokens']:,} in / {record['output_tokens']:,} out, "
                  f"${record['cost_usd']:.5f}, {record['seconds']}s")

    # The output files cover every article done with this setup, including earlier runs
    claim_rows, summary_rows, failed = [], [], []
    for article in articles:
        record = records.get((article["article_id"], setup_hash))
        if record is None:
            continue
        if record["error"]:
            failed.append(article["article_id"])
        # Claims are numbered within their passage, like FENICE's IDs (6.1_p001_c01)
        for passage_id in article["passages"]:
            passage_claims = [c["claim"] for c in record["claims"] if c["passage_id"] == passage_id]
            for i, claim in enumerate(passage_claims, 1):
                claim_rows.append({
                    "event_id": article["event_id"],
                    "article_id": article["article_id"],
                    "passage_id": passage_id,
                    "claim_id": f"{passage_id}_c{i:02d}",
                    "claim": claim,
                    "passage_text": article["passages"][passage_id],
                    "source_url": article["source_url"],
                })
        summary_rows.append({
            "Event ID": article["event_id"],
            "Article ID": article["article_id"],
            "Source URL": article["source_url"],
            "Passages": len(article["passages"]),
            "Article Words": record["article_words"],
            "Claims Extracted": len(record["claims"]),
            "Input Tokens": record["input_tokens"],
            "Output Tokens": record["output_tokens"],
            "Cost (USD)": round(record["cost_usd"], 6),
            "Seconds": record["seconds"],
            "Error": record["error"] or "",
        })
    if not summary_rows:
        print("Nothing extracted yet.")
        return

    summary = pd.DataFrame(summary_rows)
    total = {
        "Event ID": "", "Article ID": "TOTAL", "Source URL": f"{len(summary)} articles",
        **{column: summary[column].sum() for column in
           ["Passages", "Article Words", "Claims Extracted", "Input Tokens", "Output Tokens"]},
        "Cost (USD)": round(summary["Cost (USD)"].sum(), 6),
        "Seconds": round(summary["Seconds"].sum(), 2),
        "Error": f"{len(failed)} failed" if failed else "",
    }
    summary = pd.concat([summary, pd.DataFrame([total])], ignore_index=True)

    pd.DataFrame(claim_rows, columns=CLAIM_COLUMNS).to_csv(CLAIMS_FILE, index=False, encoding="utf-8-sig")
    summary.to_csv(COST_SUMMARY, index=False, encoding="utf-8-sig")

    print(f"\nTOTAL: {total['Source URL']}, {total['Claims Extracted']} claims, "
          f"{total['Input Tokens']:,} input tokens, {total['Output Tokens']:,} output tokens, "
          f"${total['Cost (USD)']:.4f}, {total['Seconds']}s")
    if failed:
        print(f"Failed: {', '.join(failed)}. Run the same command again to retry them.")
    print(f"\nClaims:       {CLAIMS_FILE}")
    print(f"Cost summary: {COST_SUMMARY}")
    print(f"Run log:      {RUN_LOG}")


if __name__ == "__main__":
    main()
