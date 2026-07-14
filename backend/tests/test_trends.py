from app.trends import clean_text, extract_hashtags, slugify


def test_clean_text_strips_urls_mentions_and_hashmarks():
    text = "Check this out https://example.com/x @someone #CoolStuff  extra   spaces"
    assert clean_text(text) == "Check this out CoolStuff extra spaces"


def test_clean_text_handles_empty_input():
    assert clean_text("") == ""
    assert clean_text(None) == ""


def test_extract_hashtags_returns_all_tags():
    assert extract_hashtags("Loving #AI and #MachineLearning today") == ["#AI", "#MachineLearning"]


def test_extract_hashtags_empty_when_none_present():
    assert extract_hashtags("No tags here") == []


def test_slugify_lowercases_and_replaces_nonalnum():
    assert slugify("Sustainable Fashion!!") == "sustainable_fashion"


def test_slugify_falls_back_to_trend_when_empty():
    assert slugify("###") == "trend"


from app.trends import extract_simple_keywords, extract_tfidf_keywords


def test_extract_simple_keywords_ranks_by_frequency():
    text = "sustainable fashion sustainable fashion recycled materials"
    keywords = extract_simple_keywords(text, top_n=2)
    assert keywords == ["sustainable", "fashion"]


def test_extract_simple_keywords_drops_stopwords_and_short_words():
    text = "this is a really cool and new AI tool for the team"
    keywords = extract_simple_keywords(text, top_n=10)
    assert "this" not in keywords
    assert "AI".lower() not in [k for k in keywords if len(k) <= 2]


def test_extract_tfidf_keywords_returns_terms_from_corpus():
    texts = [
        "Sustainable fashion brands are leading the recycled materials movement this year",
        "Recycled materials and sustainable fashion are reshaping the industry this season",
        "Slow fashion advocates push recycled materials over fast fashion waste",
    ]
    keywords = extract_tfidf_keywords(texts, top_n=5)
    assert len(keywords) > 0
    assert any("fashion" in k or "recycled" in k for k in keywords)


def test_extract_tfidf_keywords_empty_when_no_texts_pass_length_filter():
    assert extract_tfidf_keywords(["short", "tiny", ""], top_n=5) == []
