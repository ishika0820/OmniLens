from app.news_provider import get_related_articles

reference_url = (
    "https://beebom.com/"
    "nvidia-president-ceo-jensen-huang-resigns/"
)

result = get_related_articles(
    reference_url,
    max_articles=5
)

reference = result["reference_article"]
candidates = result["candidate_articles"]

print("\nEVENT ID:", result["event_id"])

print("\nREFERENCE ARTICLE:")
print("Title:", reference["title"])
print("Text length:", len(reference["text"]))

print("\nCANDIDATE ARTICLES:", len(candidates))

for i, article in enumerate(candidates, 1):
    print(f"\n{i}. {article['title']}")
    print("Publisher:", article["publisher"])
    print("Text length:", len(article["text"]))
    print("URL:", article["url"])