from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_x_trending_returns_503_without_token(monkeypatch):
    monkeypatch.setattr("app.main.trends.X_BEARER_TOKEN", None)
    response = client.get("/api/trends/x", params={"woeid": "1"})
    assert response.status_code == 503
    assert "X_BEARER_TOKEN" in response.json()["detail"]


def test_x_trending_returns_topics_when_configured(monkeypatch):
    monkeypatch.setattr("app.main.trends.X_BEARER_TOKEN", "test-token")
    with patch("app.main.trends.get_trending_topics", return_value=["#AI", "#MarketingTips"]):
        response = client.get("/api/trends/x", params={"woeid": "1", "limit": 10})
    assert response.status_code == 200
    assert response.json() == ["#AI", "#MarketingTips"]


def test_x_search_returns_rows_when_configured(monkeypatch):
    monkeypatch.setattr("app.main.trends.X_BEARER_TOKEN", "test-token")
    sample_row = {
        "platform": "X", "trend": "#AI", "post_id": "1", "post_url": "https://x.com/i/web/status/1",
        "original_text": "AI is everywhere", "keywords": ["ai"], "hashtags": ["#AI"],
        "likes": 1, "comments": 0, "retweets": 0, "quotes": 0, "engagement_score": 1,
        "created_at": "", "tracked_link": "https://x.example?utm_source=twitter",
        "rewritten_caption": "AI is having a moment.", "buffer_text": "AI is having a moment. https://x.example",
        "tags": ["ai"],
    }
    with patch("app.main.trends.build_x_rows", return_value=[sample_row]):
        response = client.get("/api/trends/x/search", params={
            "query": "#AI", "base_link": "https://yourdomain.com/blog", "campaign_name": "trend_roundup",
        })
    assert response.status_code == 200
    assert response.json() == [sample_row]


def test_instagram_search_returns_503_without_credentials(monkeypatch):
    monkeypatch.setattr("app.main.trends.IG_ACCESS_TOKEN", None)
    monkeypatch.setattr("app.main.trends.IG_BUSINESS_ACCOUNT_ID", None)
    response = client.get("/api/trends/instagram", params={
        "hashtag": "ai", "base_link": "https://yourdomain.com/blog", "campaign_name": "trend_roundup",
    })
    assert response.status_code == 503


def test_threads_search_returns_503_without_token(monkeypatch):
    monkeypatch.setattr("app.main.trends.THREADS_ACCESS_TOKEN", None)
    response = client.get("/api/trends/threads", params={
        "keyword": "ai", "base_link": "https://yourdomain.com/blog", "campaign_name": "trend_roundup",
    })
    assert response.status_code == 503


def test_manual_paste_returns_rows():
    sample_row = {
        "platform": "X", "trend": "#AI", "post_id": "", "post_url": "",
        "original_text": "AI tools everywhere", "keywords": ["ai"], "hashtags": [],
        "likes": 0, "comments": 0, "retweets": 0, "quotes": 0, "engagement_score": 0,
        "created_at": "", "tracked_link": "https://x.example?utm_source=x",
        "rewritten_caption": "AI is booming.", "buffer_text": "AI is booming. https://x.example",
        "tags": ["ai"],
    }
    with patch("app.main.trends.build_manual_rows", return_value=[sample_row]):
        response = client.post("/api/trends/manual", json={
            "base_link": "https://yourdomain.com/blog",
            "campaign_name": "trend_roundup",
            "use_ai_rewrite": True,
            "entries": [{"trend": "#AI", "platform": "X", "text": "AI tools everywhere"}],
        })
    assert response.status_code == 200
    assert response.json() == [sample_row]


def test_manual_paste_returns_empty_list_for_no_entries():
    response = client.post("/api/trends/manual", json={
        "base_link": "https://yourdomain.com/blog",
        "campaign_name": "trend_roundup",
        "use_ai_rewrite": True,
        "entries": [],
    })
    assert response.status_code == 200
    assert response.json() == []


def test_video_prompt_returns_generated_prompt():
    with patch("app.main.trends.rewrite_video_prompt_with_claude", return_value="Cinematic shot of sneakers."):
        response = client.post("/api/trends/video-prompt", json={
            "trend": "#SneakerDrop",
            "keywords": ["sneakers", "limited edition"],
            "original_text": "New sneaker drop is everywhere",
        })
    assert response.status_code == 200
    assert response.json() == {"prompt": "Cinematic shot of sneakers."}


SAMPLE_EXPORT_ROW = {
    "platform": "X", "trend": "#AI", "post_id": "1", "post_url": "https://x.com/i/web/status/1",
    "original_text": "AI is everywhere", "keywords": ["ai"], "hashtags": ["#AI"],
    "likes": 1, "comments": 0, "retweets": 0, "quotes": 0, "engagement_score": 1,
    "created_at": "", "tracked_link": "https://x.example?utm_source=twitter",
    "rewritten_caption": "AI is having a moment.", "buffer_text": "AI is having a moment. https://x.example",
    "tags": ["ai"],
}


def test_export_buffer_returns_csv():
    response = client.post("/api/trends/export", json={
        "rows": [SAMPLE_EXPORT_ROW], "format": "buffer", "gap_minutes": 90,
    })
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Text,Image URL,Tags,Posting Time" in response.text


def test_export_full_returns_csv():
    response = client.post("/api/trends/export", json={
        "rows": [SAMPLE_EXPORT_ROW], "format": "full", "gap_minutes": 90,
    })
    assert response.status_code == 200
    assert "Platform" in response.text


def test_export_rejects_unknown_format():
    response = client.post("/api/trends/export", json={
        "rows": [SAMPLE_EXPORT_ROW], "format": "xml", "gap_minutes": 90,
    })
    assert response.status_code == 422
