from app.news_provider import get_related_articles
from app.claim_extractor import FeniceClaimExtractor


REFERENCE_URL = (
    "https://beebom.com/"
    "nvidia-president-ceo-jensen-huang-resigns/"
)

print("Retrieving articles from Event Registry...")

result = get_related_articles(
    REFERENCE_URL,
    max_articles=1
)

candidates = result["candidate_articles"]

if not candidates:
    raise RuntimeError("No candidate articles returned.")

candidate = candidates[0]

print("\nCANDIDATE ARTICLE")
print("Title:", candidate["title"])
print("Publisher:", candidate["publisher"])
print("Text length:", len(candidate["text"]))

# Load the model once.
extractor = FeniceClaimExtractor()

print("\nExtracting claims...")

claims = extractor.extract_claims(
    candidate["text"]
)

print("\nTotal claims:", len(claims))

for claim in claims:
    print("\n" + "=" * 65)
    print("Claim ID:", claim["claim_id"])
    print("Claim:", claim["text"])
    print("Source chunk:", claim["chunk_index"])