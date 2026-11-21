import re

BOILERPLATE_PATTERNS = [
    r"\ball rights reserved\b",
    r"\bprivacy policy\b",
    r"\bterms (?:of|and) (?:use|service)\b",
    r"\btrademarks? (?:of|and/or)\b",
    r"\bcopyright\b",
    r"©",
    r"\bsubscribe to (?:our|the)\b",
    r"\bsign up for (?:our|the)\b",
    r"\bcontact us\b",
]


def clean_claims(claims):
    """
    Remove obvious non-claims, incomplete fragments,
    boilerplate, and duplicate claims.

    Preserves claim IDs, source chunks, chunk indices,
    and other metadata for accepted claims.

    Returns:
        cleaned: List of accepted claims.
        removed: List of rejected claims with reasons.
    """

    cleaned = []
    removed = []
    seen = set()

    for claim in claims:
        text = re.sub(
            r"\s+",
            " ",
            claim.get("text") or ""
        ).strip()

        reason = None

        # 1. Remove empty claims
        if not text:
            reason = "empty"

        # 2. Remove boilerplate
        elif any(
            re.search(pattern, text, re.IGNORECASE)
            for pattern in BOILERPLATE_PATTERNS
        ):
            reason = "boilerplate"

        # 3. Remove very short fragments
        elif len(text.split()) < 4:
            reason = "too_short"

        # 4. Remove fragments ending in an apostrophe
        elif text.endswith(("'", "’")):
            reason = "incomplete_fragment"

        # 5. Remove obvious noun-phrase fragments
        # without attempting broad grammatical filtering
        elif re.fullmatch(
            r"(?:[\w.'’\-]+\s+){1,6}"
            r"(?:leadership team|management team)\.",
            text,
            re.IGNORECASE
        ):
            reason = "incomplete_fragment"

        # 6. Remove exact normalized duplicates
        else:
            normalized = re.sub(
                r"[^\w\s]",
                "",
                text.casefold()
            )

            normalized = re.sub(
                r"\s+",
                " ",
                normalized
            ).strip()

            if normalized in seen:
                reason = "duplicate"
            else:
                seen.add(normalized)

        if reason:
            removed.append({
                **claim,
                "removal_reason": reason
            })

        else:
            cleaned.append({
                **claim,
                "text": text
            })

    return cleaned, removed