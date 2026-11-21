from app.article_cleaner import clean_article_text

STORY = (
    "The city council approved a $2 billion transit plan on Tuesday.\n\n"
    "The plan adds three new light-rail lines over the next decade.\n\n"
    "Mayor Jane Doe said construction would begin next spring.\n\n"
    "Critics argued the budget was underestimated by at least 20 percent."
)


def test_cuts_more_like_this_section():
    text = STORY + "\n\nMore like this\n\nStock markets fall on rate fears\n\nCelebrity wedding draws crowds"
    cleaned = clean_article_text(text)
    assert cleaned == STORY
    assert "Stock markets" not in cleaned


def test_cuts_related_articles_with_colon():
    text = STORY + "\n\nRelated Articles:\nHurricane season begins early"
    assert clean_article_text(text) == STORY


def test_cuts_you_may_also_like():
    text = STORY + "\nYou may also like\nTen best beaches in Europe"
    assert clean_article_text(text) == STORY


def test_removes_inline_read_more_line():
    text = (
        "The city council approved a $2 billion transit plan on Tuesday.\n\n"
        "READ MORE: Governor signs unrelated tax bill\n\n"
        "The plan adds three new light-rail lines over the next decade."
    )
    cleaned = clean_article_text(text)
    assert "Governor" not in cleaned
    assert "light-rail" in cleaned


def test_keeps_sentences_that_mention_related():
    text = STORY + "\n\nOfficials said related projects would be reviewed in May."
    assert "related projects" in clean_article_text(text)


def test_heading_near_top_does_not_wipe_article():
    text = "Related\n\n" + STORY
    assert "Critics argued" in clean_article_text(text)


def test_empty_text():
    assert clean_article_text("") == ""