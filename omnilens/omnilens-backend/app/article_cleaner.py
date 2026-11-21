import re
_TRAILING_SECTION_HEADINGS = [
    r"more like this",
    r"more (?:from|on|about)\b.*",
    r"more (?:stories|news|articles|coverage|to read|top stories)",
    r"related(?: articles?| stories| news| coverage| content| reading| links| topics)?",
    r"you (?:might|may) (?:also )?(?:like|enjoy|be interested in)",
    r"recommended(?: for you| stories| articles| reading| videos)?",
    r"(?:what to )?read (?:more|next|this next)",
    r"(?:most|top) (?:popular|read|viewed|shared)(?: stories| articles)?",
    r"trending(?: now| stories| news)?",
    r"popular (?:stories|articles|now)",
    r"(?:also|further|recommended) reading",
    r"see also",
    r"don'?t miss",
    r"top stories",
    r"latest (?:news|stories|headlines)",
    r"other (?:news|stories)",
    r"up next",
    r"keep reading",
    r"editor'?s picks",
    r"around the web",
    r"sponsored(?: content| stories)?",
]

_HEADING_LINE = re.compile(
    r"^\s*(?:" + "|".join(_TRAILING_SECTION_HEADINGS) + r")\s*[:\-–—]?\s*$",
    re.IGNORECASE,
)

# Single promo lines that can appear anywhere in the body,
# e.g. "READ MORE: Senate passes bill" or "Also read: ...".
_INLINE_PROMO_LINE = re.compile(
    r"^\s*(?:read more|also read|read also|related|see also|"
    r"more like this|recommended|watch|listen|click here)\s*[:|\-–—]\s+.*$",
    re.IGNORECASE,
)

# A trailing heading is only trusted once this much of the article has
# passed, so a short line near the top can never wipe out the story.
_MIN_FRACTION_BEFORE_CUT = 0.3


def _truncate_trailing_sections(text: str) -> str:
    """Cut the text at the first 'More like this'-style heading."""
    position = 0
    for line in text.splitlines(keepends=True):
        if (
            _HEADING_LINE.match(line)
            and position >= len(text) * _MIN_FRACTION_BEFORE_CUT
        ):
            return text[:position]
        position += len(line)
    return text




def clean_article_text(text: str) -> str:
    """
    Remove clearly marked recommendation blocks
    before sending article text to FENICE.
    """
    if not text:
        return ""
    text = _truncate_trailing_sections(text)

    # Remove standalone related-article recommendation blocks.
    text = re.sub(
        r"(?im)^\s*You Might Also Like:\s*\n"
        r"(?:[ \t]*\n)*"
        r"[^\n]*(?:\n|$)",
        "\n",
        text

    )
    text = "\n".join(
        line for line in text.split("\n")
        if not _INLINE_PROMO_LINE.match(line)
    )

    # Remove common standalone page boilerplate.
    text = re.sub(
        r"(?im)^\s*(?:All rights reserved\.?|"
        r"Subscribe to our newsletter|"
        r"Read more articles)\s*$",
        "",
        text
    )

    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()