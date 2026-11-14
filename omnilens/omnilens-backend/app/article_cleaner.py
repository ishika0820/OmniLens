import re


def clean_article_text(text: str) -> str:
    """
    Remove clearly marked recommendation blocks
    before sending article text to FENICE.
    """
    if not text:
        return ""

    # Remove standalone related-article recommendation blocks.
    text = re.sub(
        r"(?im)^\s*You Might Also Like:\s*\n"
        r"(?:[ \t]*\n)*"
        r"[^\n]*(?:\n|$)",
        "\n",
        text
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