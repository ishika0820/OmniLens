from datetime import datetime, timezone

from app.news_provider import get_related_articles
from app.claim_extractor import FeniceClaimExtractor
from app.claim_cleaner import clean_claims
from app.article_cleaner import clean_article_text


class OmniLensPipeline:
    def __init__(self):
        # Load FENICE once and reuse it.
        self.extractor = FeniceClaimExtractor()

    def analyze(self, reference_url, max_articles=5):
        # Step 1: Discover related articles.
        news_data = get_related_articles(
            reference_url,
            max_articles=max_articles
        )

        reference = news_data["reference_article"]

        if not reference["text"].strip():
            raise ValueError(
                "Reference article has no usable text."
            )

        candidates = news_data["candidate_articles"]

        if not candidates:
            raise ValueError(
                "No related articles with usable text found."
            )

        # Step 2: Extract claims from each candidate.
        processed_articles = []
        total_claims = 0

        for index, article in enumerate(candidates, start=1):
            print(
                f"Processing article {index}/{len(candidates)}: "
                f"{article['title']}",
                flush=True
            )

            try:
                cleaned_text = clean_article_text(article["text"])

                raw_claims = self.extractor.extract_claims(
                    cleaned_text
                )

                claims, removed_claims = clean_claims(raw_claims)

                # Unique IDs across the whole analysis.
                for claim_index, claim in enumerate(claims, start=1):
                    claim["claim_id"] = (
                        f"A{index:03d}_C{claim_index:03d}"
                    )
                    claim["article_id"] = article["article_id"]

                processed_articles.append({
                    **article,
                    "extraction_status": "success",
                    "claims": claims,
                    "claim_count": len(claims),
                    "raw_claim_count": len(raw_claims),
                    "removed_claim_count": len(removed_claims),
                    "removed_claims": removed_claims
                })

                total_claims += len(claims)

            except Exception as exc:
                print(
                    f"Extraction failed for {article['title']}: {exc}",
                    flush=True
                )

                processed_articles.append({
                    **article,
                    "extraction_status": "failed",
                    "extraction_error": str(exc),
                    "claims": [],
                    "claim_count": 0
                })

        return {
            "pipeline_version": "1.1",
            "status": "extraction_complete",
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "event_id": news_data["event_id"],
            "reference_article": reference,
            "candidate_articles": processed_articles,
            "summary": {
                "articles_found": len(candidates),
                "articles_processed": sum(
                    a["extraction_status"] == "success"
                    for a in processed_articles
                ),
                "total_claims": total_claims
            }
        }