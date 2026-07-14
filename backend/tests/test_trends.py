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
