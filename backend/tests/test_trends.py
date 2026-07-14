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
