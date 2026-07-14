from unittest.mock import patch

from app.trends import build_manual_rows, build_meta_rows, build_x_rows

X_POSTS = [
    {
        "id": "1",
        "text": "Sustainable fashion brands are leading the recycled materials movement",
        "created_at": "2026-07-01T00:00:00Z",
        "public_metrics": {"like_count": 5, "reply_count": 1, "retweet_count": 1, "quote_count": 0},
    },
    {
        "id": "2",
        "text": "Recycled materials are reshaping the fashion industry this season",
        "created_at": "2026-07-01T01:00:00Z",
        "public_metrics": {"like_count": 20, "reply_count": 3, "retweet_count": 4, "quote_count": 1},
    },
]


def test_build_x_rows_ranks_by_engagement_and_fills_row_shape():
    with patch("app.trends.search_recent_posts", return_value=X_POSTS), \
         patch("app.trends.rewrite_caption_with_claude", return_value="Rewritten caption"):
        rows = build_x_rows(
            trend="#SustainableFashion",
            base_link="https://yourdomain.com/blog",
            campaign_name="trend_roundup",
            posts_per_trend=25,
            output_posts_per_trend=2,
            use_ai_rewrite=True,
        )

    assert len(rows) == 2
    assert rows[0]["post_id"] == "2"  # higher engagement first
    assert rows[0]["platform"] == "X"
    assert rows[0]["rewritten_caption"] == "Rewritten caption"
    assert "utm_campaign=trend_roundup" in rows[0]["tracked_link"]
    assert rows[0]["buffer_text"].startswith("Rewritten caption")


def test_build_x_rows_returns_empty_when_no_posts():
    with patch("app.trends.search_recent_posts", return_value=[]):
        rows = build_x_rows(
            trend="#Nothing",
            base_link="https://yourdomain.com/blog",
            campaign_name="trend_roundup",
            posts_per_trend=25,
            output_posts_per_trend=2,
            use_ai_rewrite=False,
        )
    assert rows == []


def test_build_meta_rows_normalizes_instagram_caption_field():
    ig_posts = [{"id": "1", "caption": "Loving recycled materials", "like_count": 5, "comments_count": 1, "permalink": "https://instagram.com/p/1", "timestamp": "2026-07-01"}]
    with patch("app.trends.search_instagram_hashtag", return_value=ig_posts), \
         patch("app.trends.rewrite_caption_with_claude", return_value="Rewritten"):
        rows = build_meta_rows(
            platform="Instagram",
            query="sustainablefashion",
            base_link="https://yourdomain.com/blog",
            campaign_name="trend_roundup",
            posts_per_query=25,
            output_posts_per_query=1,
            use_ai_rewrite=True,
        )
    assert rows[0]["platform"] == "Instagram"
    assert rows[0]["original_text"] == "Loving recycled materials"
    assert rows[0]["post_url"] == "https://instagram.com/p/1"


def test_build_manual_rows_groups_keywords_by_trend():
    entries = [
        {"trend": "#AI", "platform": "X", "text": "AI tools are booming this quarter across every industry"},
        {"trend": "#AI", "platform": "Instagram", "text": "AI tools booming everywhere this quarter, huge industry shift"},
    ]
    with patch("app.trends.rewrite_caption_with_claude", return_value="Rewritten"):
        rows = build_manual_rows(
            entries=entries,
            base_link="https://yourdomain.com/blog",
            campaign_name="trend_roundup",
            use_ai_rewrite=True,
        )
    assert len(rows) == 2
    assert rows[0]["trend"] == "#AI"
    assert rows[0]["post_id"] == ""
