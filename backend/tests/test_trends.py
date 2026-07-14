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


import csv
import io

from app.trends import build_tracked_link, make_buffer_csv, make_full_export_csv

SAMPLE_ROW = {
    "platform": "X",
    "trend": "#AI",
    "post_id": "123",
    "post_url": "https://x.com/i/web/status/123",
    "original_text": "AI is everywhere",
    "keywords": ["ai", "tools"],
    "hashtags": ["#AI"],
    "likes": 10,
    "comments": 2,
    "retweets": 3,
    "quotes": 0,
    "engagement_score": 16,
    "created_at": "2026-07-01T00:00:00Z",
    "tracked_link": "https://yourdomain.com/blog?utm_source=twitter&utm_medium=social&utm_campaign=trend_roundup&utm_content=ai",
    "rewritten_caption": "AI is having a moment. Here's what's worth knowing.",
    "buffer_text": "AI is having a moment. Here's what's worth knowing. https://yourdomain.com/blog?utm_source=twitter",
    "tags": ["ai", "tools"],
}


def test_build_tracked_link_uses_question_mark_when_no_query_string():
    link = build_tracked_link("https://yourdomain.com/blog", "Trend Roundup", "#AI")
    assert link.startswith("https://yourdomain.com/blog?utm_source=twitter")
    assert "utm_campaign=trend_roundup" in link
    assert "utm_content=ai" in link


def test_build_tracked_link_uses_ampersand_when_query_string_present():
    link = build_tracked_link("https://yourdomain.com/blog?ref=site", "Trend Roundup", "#AI")
    assert "?ref=site&utm_source=twitter" in link


def test_make_buffer_csv_has_expected_columns_and_row_count():
    csv_bytes = make_buffer_csv([SAMPLE_ROW, SAMPLE_ROW], gap_minutes=90)
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
    rows = list(reader)
    assert reader.fieldnames == ["Text", "Image URL", "Tags", "Posting Time"]
    assert len(rows) == 2
    assert rows[0]["Text"] == SAMPLE_ROW["buffer_text"]
    assert rows[0]["Tags"] == "ai,tools"


def test_make_buffer_csv_staggers_posting_times():
    csv_bytes = make_buffer_csv([SAMPLE_ROW, SAMPLE_ROW], gap_minutes=90)
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
    rows = list(reader)
    assert rows[0]["Posting Time"] != rows[1]["Posting Time"]


def test_make_full_export_csv_includes_all_row_fields():
    csv_bytes = make_full_export_csv([SAMPLE_ROW])
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
    rows = list(reader)
    assert rows[0]["Platform"] == "X"
    assert rows[0]["Trend"] == "#AI"
    assert rows[0]["Likes"] == "10"


import requests_mock

from app.trends import rewrite_with_claude, template_rewrite, template_video_prompt


def test_template_rewrite_includes_theme_and_hashtags():
    text = template_rewrite("#SustainableFashion", ["eco-friendly", "recycled materials"])
    assert "Eco-friendly" in text or "eco-friendly" in text.lower()
    assert "#SustainableFashion" in text or "#Sustainablefashion".lower() in text.lower()


def test_template_video_prompt_is_visual_not_marketing():
    text = template_video_prompt("#SustainableFashion", ["eco-friendly", "recycled materials"])
    assert "eco-friendly" in text.lower()
    assert "read more" not in text.lower()
    assert "#" not in text


def test_rewrite_with_claude_returns_fallback_when_no_api_key(monkeypatch):
    monkeypatch.setattr("app.trends.ANTHROPIC_API_KEY", None)
    result = rewrite_with_claude("some prompt", fallback="fallback text")
    assert result == "fallback text"


def test_rewrite_with_claude_returns_model_text_on_success(monkeypatch):
    monkeypatch.setattr("app.trends.ANTHROPIC_API_KEY", "test-key")
    with requests_mock.Mocker() as mock:
        mock.post(
            "https://api.anthropic.com/v1/messages",
            json={"content": [{"type": "text", "text": "Rewritten output"}]},
        )
        result = rewrite_with_claude("some prompt", fallback="fallback text")
    assert result == "Rewritten output"


def test_rewrite_with_claude_returns_fallback_on_http_error(monkeypatch):
    monkeypatch.setattr("app.trends.ANTHROPIC_API_KEY", "test-key")
    with requests_mock.Mocker() as mock:
        mock.post("https://api.anthropic.com/v1/messages", status_code=500)
        result = rewrite_with_claude("some prompt", fallback="fallback text")
    assert result == "fallback text"


from app.trends import engagement_score, get_trending_topics, post_url, search_recent_posts


def test_post_url_builds_x_status_link():
    assert post_url("123") == "https://x.com/i/web/status/123"


def test_engagement_score_weights_retweets_and_quotes_double():
    post = {"public_metrics": {"like_count": 10, "reply_count": 2, "retweet_count": 3, "quote_count": 1}}
    assert engagement_score(post) == 10 + 2 + 3 * 2 + 1 * 2


def test_engagement_score_handles_missing_metrics():
    assert engagement_score({}) == 0


def test_get_trending_topics_parses_trend_names(monkeypatch):
    monkeypatch.setattr("app.trends.X_BEARER_TOKEN", "test-token")
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.x.com/2/trends/by/woeid/1",
            json={"data": [{"trend_name": "#AI"}, {"name": "#MarketingTips"}]},
        )
        topics = get_trending_topics(woeid="1", limit=10)
    assert topics == ["#AI", "#MarketingTips"]


def test_search_recent_posts_returns_data_list(monkeypatch):
    monkeypatch.setattr("app.trends.X_BEARER_TOKEN", "test-token")
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.x.com/2/tweets/search/recent",
            json={"data": [{"id": "1", "text": "hello"}]},
        )
        posts = search_recent_posts("#AI", max_results=10)
    assert posts == [{"id": "1", "text": "hello"}]


from app.trends import ig_find_hashtag_id, ig_get_hashtag_media, search_instagram_hashtag


def test_ig_find_hashtag_id_returns_first_match(monkeypatch):
    monkeypatch.setattr("app.trends.IG_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr("app.trends.IG_BUSINESS_ACCOUNT_ID", "12345")
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://graph.facebook.com/v19.0/ig_hashtag_search",
            json={"data": [{"id": "999"}]},
        )
        hashtag_id = ig_find_hashtag_id("#sustainablefashion")
    assert hashtag_id == "999"


def test_ig_find_hashtag_id_returns_none_when_no_match(monkeypatch):
    monkeypatch.setattr("app.trends.IG_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr("app.trends.IG_BUSINESS_ACCOUNT_ID", "12345")
    with requests_mock.Mocker() as mock:
        mock.get("https://graph.facebook.com/v19.0/ig_hashtag_search", json={"data": []})
        assert ig_find_hashtag_id("nonexistent") is None


def test_ig_get_hashtag_media_returns_limited_list(monkeypatch):
    monkeypatch.setattr("app.trends.IG_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr("app.trends.IG_BUSINESS_ACCOUNT_ID", "12345")
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://graph.facebook.com/v19.0/999/top_media",
            json={"data": [{"id": "1"}, {"id": "2"}]},
        )
        media = ig_get_hashtag_media("999", limit=1)
    assert media == [{"id": "1"}]


def test_search_instagram_hashtag_returns_empty_when_hashtag_not_found(monkeypatch):
    monkeypatch.setattr("app.trends.IG_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr("app.trends.IG_BUSINESS_ACCOUNT_ID", "12345")
    with requests_mock.Mocker() as mock:
        mock.get("https://graph.facebook.com/v19.0/ig_hashtag_search", json={"data": []})
        assert search_instagram_hashtag("nope") == []


from app.trends import search_threads_keyword


def test_search_threads_keyword_returns_limited_list(monkeypatch):
    monkeypatch.setattr("app.trends.THREADS_ACCESS_TOKEN", "test-token")
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://graph.threads.net/v1.0/keyword_search",
            json={"data": [{"id": "1"}, {"id": "2"}, {"id": "3"}]},
        )
        results = search_threads_keyword("sustainable fashion", limit=2)
    assert results == [{"id": "1"}, {"id": "2"}]
