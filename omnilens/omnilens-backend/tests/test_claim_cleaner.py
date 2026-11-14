from app.claim_cleaner import clean_claims


def test_removes_obvious_nonclaims():
    claims = [
        {"text": "Colette Kress"},
        {"text": "All rights reserved."},
        {"text": "Colette Kress'"},
        {
            "text": (
                "NVIDIA appointed Colette Kress "
                "as interim CEO."
            )
        }
    ]

    cleaned, removed = clean_claims(claims)

    assert len(cleaned) == 1
    assert len(removed) == 3
    assert "interim CEO" in cleaned[0]["text"]


def test_removes_exact_duplicates():
    claims = [
        {
            "text": (
                "NVIDIA appointed Colette Kress "
                "as interim CEO."
            )
        },
        {
            "text": (
                "NVIDIA appointed Colette Kress "
                "as interim CEO!"
            )
        }
    ]

    cleaned, removed = clean_claims(claims)

    assert len(cleaned) == 1
    assert removed[0]["removal_reason"] == "duplicate"


def test_preserves_source_metadata():
    claims = [
        {
            "claim_id": "C001",
            "text": "NVIDIA appointed Colette Kress as interim CEO.",
            "source_chunk": "Original passage",
            "chunk_index": 2
        }
    ]

    cleaned, removed = clean_claims(claims)

    assert len(removed) == 0
    assert cleaned[0]["claim_id"] == "C001"
    assert cleaned[0]["source_chunk"] == "Original passage"
    assert cleaned[0]["chunk_index"] == 2