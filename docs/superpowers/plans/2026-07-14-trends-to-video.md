# Trending Keywords → Video Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users fetch trending posts (X, Instagram, Threads, or manually pasted), derive an AI video-generation prompt from them, and generate a video variation through the existing (now-corrected) Seedance/Ark pipeline — plus export a Buffer bulk-upload CSV, matching `app.py`'s feature set.

**Architecture:** A new `backend/app/trends.py` module holds pure, testable functions ported from `app.py` (fetch, keyword-extraction, rewrite, CSV). New FastAPI routes in `backend/app/main.py` wrap those functions and return/accept a shared `TrendRow` shape. `create_variation` in `main.py` is rewritten to use Ark's real async task-submit/poll contract instead of a single synchronous multipart call. The React frontend gets a new "Trends" section that calls these routes and can push a generated prompt into the existing Generator form.

**Tech Stack:** FastAPI, httpx, requests, pandas, scikit-learn (backend); React 18 + Vite (frontend); pytest + pytest-asyncio + respx + requests-mock (backend tests, newly added).

## Global Constraints

- No Streamlit anywhere in the shipped product — `trends.py` functions must have zero `streamlit` imports.
- Facebook is explicitly out of scope — no route, no UI option for it.
- No new database — manual-paste queue and Instagram hashtag-cap tracking are React state only, no backend persistence.
- Every trends route must return `503` with a descriptive message (not an unhandled exception) when its required env var(s) are missing.
- The existing `/api/variations` request/response contract (multipart upload in, `VariationResponse` out) does not change — only what happens *inside* `create_variation` changes.
- Video-to-video only — no text-to-video capability is being added.

---

## Task 1: Backend test tooling + `trends.py` text helpers

**Files:**
- Create: `backend/requirements-dev.txt`
- Create: `backend/pytest.ini`
- Create: `backend/app/trends.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_trends.py`

**Interfaces:**
- Produces: `clean_text(text: str) -> str`, `extract_hashtags(text: str) -> list[str]`, `slugify(text: str) -> str` in `backend/app/trends.py`

- [ ] **Step 1: Create dev requirements**

`backend/requirements-dev.txt`:
```
-r requirements.txt
pytest==8.3.3
pytest-asyncio==0.24.0
requests-mock==1.12.1
respx==0.21.1
```

- [ ] **Step 2: Create pytest config**

`backend/pytest.ini`:
```ini
[pytest]
testpaths = tests
asyncio_mode = auto
```

- [ ] **Step 3: Install dev dependencies**

Run: `cd backend && .venv/Scripts/pip install -r requirements-dev.txt`
Expected: install succeeds with no errors.

- [ ] **Step 4: Write failing tests for text helpers**

`backend/tests/__init__.py` (empty file).

`backend/tests/test_trends.py`:
```python
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
```

- [ ] **Step 5: Run tests, verify they fail with import error**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.trends'`

- [ ] **Step 6: Implement the text helpers**

`backend/app/trends.py`:
```python
import re


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_hashtags(text: str) -> list[str]:
    if not text:
        return []

    return re.findall(r"#\w+", text)


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text or "trend"
```

- [ ] **Step 7: Run tests, verify they pass**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v`
Expected: 6 passed

- [ ] **Step 8: Commit**

```bash
git add backend/requirements-dev.txt backend/pytest.ini backend/app/trends.py backend/tests/__init__.py backend/tests/test_trends.py
git commit -m "test: add backend test tooling and trends.py text helpers"
```

---

## Task 2: Keyword extraction

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/trends.py`
- Modify: `backend/tests/test_trends.py`

**Interfaces:**
- Consumes: `clean_text` from Task 1
- Produces: `STOPWORDS: set[str]`, `extract_simple_keywords(text: str, top_n: int = 5) -> list[str]`, `extract_tfidf_keywords(texts: list[str], top_n: int = 8) -> list[str]`

- [ ] **Step 1: Add pandas and scikit-learn to requirements**

Append to `backend/requirements.txt`:
```
pandas==2.2.3
scikit-learn==1.5.2
```

Run: `cd backend && .venv/Scripts/pip install -r requirements.txt`
Expected: install succeeds.

- [ ] **Step 2: Write failing tests for keyword extraction**

Append to `backend/tests/test_trends.py`:
```python
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
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v -k keyword`
Expected: FAIL — `ImportError: cannot import name 'extract_simple_keywords'`

- [ ] **Step 4: Implement keyword extraction**

Append to `backend/app/trends.py`:
```python
import string

from sklearn.feature_extraction.text import TfidfVectorizer

STOPWORDS = set("""
a an the and or but if is are was were be been being to of in on for with
as at by from this that these those it its it's im i'm you your yours we
our us they them their he she his her not no so just really very can
will would could should have has had do does did rt via new get got
about into over after before more most less much many very than then
""".split())


def extract_simple_keywords(text: str, top_n: int = 5) -> list[str]:
    text = clean_text(text)
    text = text.translate(str.maketrans("", "", string.punctuation))

    words = [
        word.lower()
        for word in text.split()
        if word.lower() not in STOPWORDS and len(word) > 2
    ]

    counts: dict[str, int] = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1

    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [word for word, _count in ranked[:top_n]]


def extract_tfidf_keywords(texts: list[str], top_n: int = 8) -> list[str]:
    cleaned_texts = []

    for text in texts:
        cleaned = clean_text(text)
        if len(cleaned) > 20:
            cleaned_texts.append(cleaned)

    if not cleaned_texts:
        return []

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        max_features=80,
    )

    try:
        matrix = vectorizer.fit_transform(cleaned_texts)
    except ValueError:
        return []

    scores = matrix.sum(axis=0).A1
    terms = vectorizer.get_feature_names_out()

    ranked = sorted(zip(terms, scores), key=lambda item: item[1], reverse=True)

    keywords = []
    for term, _score in ranked:
        term = term.strip().lower()
        if term and term not in STOPWORDS:
            keywords.append(term)

    return keywords[:top_n]
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v -k keyword`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/app/trends.py backend/tests/test_trends.py
git commit -m "feat: add TF-IDF and simple keyword extraction to trends module"
```

---

## Task 3: Link building and CSV export

**Files:**
- Modify: `backend/app/trends.py`
- Modify: `backend/tests/test_trends.py`

**Interfaces:**
- Produces: `build_tracked_link(base_url: str, campaign: str, trend: str, source: str = "twitter", medium: str = "social") -> str`, `make_buffer_csv(rows: list[dict], gap_minutes: int = 90) -> bytes`, `make_full_export_csv(rows: list[dict]) -> bytes`

`rows` in both CSV functions are `TrendRow`-shaped dicts (see Task 8) with at least these keys: `platform, trend, post_id, post_url, original_text, keywords, hashtags, likes, comments, retweets, quotes, engagement_score, created_at, tracked_link, rewritten_caption, buffer_text, tags`.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_trends.py`:
```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v -k "tracked_link or csv"`
Expected: FAIL — `ImportError: cannot import name 'build_tracked_link'`

- [ ] **Step 3: Implement link building and CSV export**

Append to `backend/app/trends.py`:
```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

SYDNEY_TZ = ZoneInfo("Australia/Sydney")


def build_tracked_link(
    base_url: str,
    campaign: str,
    trend: str,
    source: str = "twitter",
    medium: str = "social",
) -> str:
    separator = "&" if "?" in base_url else "?"

    return (
        f"{base_url}"
        f"{separator}utm_source={source}"
        f"&utm_medium={medium}"
        f"&utm_campaign={slugify(campaign)}"
        f"&utm_content={slugify(trend)}"
    )


def make_buffer_csv(rows: list[dict], gap_minutes: int = 90) -> bytes:
    now = datetime.now(SYDNEY_TZ)

    posting_times = [
        (now + timedelta(minutes=gap_minutes * (index + 1))).strftime("%Y-%m-%d %H:%M")
        for index in range(len(rows))
    ]

    buffer_df = pd.DataFrame({
        "Text": [row["buffer_text"] for row in rows],
        "Image URL": [row.get("image_url", "") for row in rows],
        "Tags": [",".join(row.get("tags", [])) for row in rows],
        "Posting Time": posting_times,
    })

    return buffer_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def make_full_export_csv(rows: list[dict]) -> bytes:
    full_df = pd.DataFrame([
        {
            "Platform": row["platform"],
            "Trend": row["trend"],
            "Post ID": row["post_id"],
            "Post URL": row["post_url"],
            "Original Text": row["original_text"],
            "Keywords": ", ".join(row.get("keywords", [])),
            "Hashtags": ", ".join(row.get("hashtags", [])),
            "Likes": row.get("likes", 0),
            "Comments": row.get("comments", 0),
            "Retweets": row.get("retweets", 0),
            "Quotes": row.get("quotes", 0),
            "Engagement Score": row.get("engagement_score", 0),
            "Created At": row.get("created_at", ""),
            "Tracked Link": row.get("tracked_link", ""),
            "Rewritten Caption": row.get("rewritten_caption", ""),
            "Buffer Text": row.get("buffer_text", ""),
            "Tags": ",".join(row.get("tags", [])),
        }
        for row in rows
    ])

    return full_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v -k "tracked_link or csv"`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/trends.py backend/tests/test_trends.py
git commit -m "feat: add tracked-link builder and Buffer/full CSV export to trends module"
```

---

## Task 4: Caption and video-prompt rewriting

**Files:**
- Modify: `backend/app/trends.py`
- Modify: `backend/tests/test_trends.py`

**Interfaces:**
- Produces: `template_rewrite(trend: str, keywords: list[str]) -> str`, `template_video_prompt(trend: str, keywords: list[str]) -> str`, `rewrite_with_claude(prompt: str, fallback: str) -> str`, `ANTHROPIC_API_KEY: str | None`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_trends.py`:
```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v -k "rewrite or template"`
Expected: FAIL — `ImportError: cannot import name 'template_rewrite'`

- [ ] **Step 3: Implement rewriting functions**

Append to `backend/app/trends.py`:
```python
import os

import requests

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def template_rewrite(trend: str, keywords: list[str]) -> str:
    clean_trend = trend.replace("#", "").strip()

    if keywords:
        theme = keywords[0].title()
        keyword_line = ", ".join(keywords[:3])
    else:
        theme = clean_trend
        keyword_line = clean_trend

    hashtags = []

    if trend.startswith("#"):
        hashtags.append(trend)
    else:
        hashtags.append("#" + re.sub(r"\W+", "", clean_trend.title()))

    for keyword in keywords[:2]:
        tag = "#" + re.sub(r"\W+", "", keyword.title())
        if len(tag) > 1:
            hashtags.append(tag)

    hashtags = list(dict.fromkeys(hashtags))[:2]

    return (
        f"{theme} is getting attention right now. "
        f"Here are the key themes to watch: {keyword_line}. "
        f"Read more "
        + " ".join(hashtags)
    )


def template_video_prompt(trend: str, keywords: list[str]) -> str:
    clean_trend = trend.replace("#", "").strip()
    subject = keywords[0].title() if keywords else clean_trend
    detail_line = ", ".join(keywords[1:4]) if len(keywords) > 1 else clean_trend

    return (
        f"Cinematic visual showcase of {subject.lower()} — {detail_line}, "
        f"natural lighting, smooth camera motion, shallow depth of field."
    )


def rewrite_with_claude(prompt: str, fallback: str) -> str:
    if not ANTHROPIC_API_KEY:
        return fallback

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-5",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        response.raise_for_status()

        content = response.json().get("content", [])
        text_blocks = [
            block.get("text", "")
            for block in content
            if block.get("type") == "text"
        ]
        rewritten = " ".join(text_blocks).strip()

        return rewritten if rewritten else fallback
    except Exception:
        return fallback


def rewrite_caption_with_claude(original_text: str, trend: str, keywords: list[str]) -> str:
    fallback = template_rewrite(trend, keywords)
    prompt = f"""
Rewrite the following social post into Buffer-ready marketing copy.

Rules:
- Keep it punchy, professional, and useful.
- Do not copy the original wording too closely.
- Keep it under 240 characters before the link.
- Use 1-2 relevant hashtags maximum.
- Avoid clickbait and emoji spam.
- Do not put quotation marks around the output.
- End with a natural CTA like "Learn more" or "Read the full insight".

Trend / topic:
{trend}

Original post:
{original_text}

Key themes:
{", ".join(keywords)}
"""
    return rewrite_with_claude(prompt, fallback)


def rewrite_video_prompt_with_claude(original_text: str, trend: str, keywords: list[str]) -> str:
    fallback = template_video_prompt(trend, keywords)
    prompt = f"""
Turn the following trending topic into a short, concrete visual-direction
prompt for AI video generation (not marketing copy).

Rules:
- Describe visual subject, mood, lighting, and motion - not hashtags or CTAs.
- 1-3 sentences, concrete and filmable.
- No quotation marks, no hashtags, no links.

Trend/topic: {trend}
Key themes: {", ".join(keywords)}
Source post (for context only): {original_text}
"""
    return rewrite_with_claude(prompt, fallback)
```

Note: `import re` already exists at the top of `trends.py` from Task 1 — do not duplicate it.

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v -k "rewrite or template"`
Expected: 5 passed

- [ ] **Step 5: Add `ANTHROPIC_API_KEY` to `.env.example`**

Append to `backend/.env.example`:
```
ANTHROPIC_API_KEY=
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/trends.py backend/tests/test_trends.py backend/.env.example
git commit -m "feat: add caption and video-prompt rewriting (Claude + template fallback)"
```

---

## Task 5: X (Twitter) fetch functions

**Files:**
- Modify: `backend/app/trends.py`
- Modify: `backend/tests/test_trends.py`

**Interfaces:**
- Produces: `X_BEARER_TOKEN: str | None`, `get_trending_topics(woeid: str, limit: int = 10) -> list[str]`, `search_recent_posts(query: str, max_results: int = 25) -> list[dict]`, `engagement_score(post: dict) -> int`, `post_url(post_id: str) -> str`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_trends.py`:
```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v -k "trending or recent_posts or engagement or post_url"`
Expected: FAIL — `ImportError: cannot import name 'get_trending_topics'`

- [ ] **Step 3: Implement X functions**

Append to `backend/app/trends.py`:
```python
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
X_API_BASE = "https://api.x.com/2"


def _x_headers() -> dict:
    return {"Authorization": f"Bearer {X_BEARER_TOKEN}"}


def get_trending_topics(woeid: str, limit: int = 10) -> list[str]:
    url = f"{X_API_BASE}/trends/by/woeid/{woeid}"
    response = requests.get(url, headers=_x_headers(), params={"max_trends": limit}, timeout=20)
    response.raise_for_status()

    data = response.json().get("data", [])

    topics = []
    for item in data:
        topic = item.get("trend_name") or item.get("name")
        if topic:
            topics.append(topic)

    return topics[:limit]


def search_recent_posts(query: str, max_results: int = 25) -> list[dict]:
    url = f"{X_API_BASE}/tweets/search/recent"
    params = {
        "query": f'"{query}" -is:retweet lang:en',
        "max_results": max_results,
        "sort_order": "recency",
        "tweet.fields": "created_at,lang,public_metrics,entities",
    }
    response = requests.get(url, headers=_x_headers(), params=params, timeout=20)
    response.raise_for_status()

    return response.json().get("data", [])


def engagement_score(post: dict) -> int:
    metrics = post.get("public_metrics", {}) or {}

    likes = metrics.get("like_count", 0)
    replies = metrics.get("reply_count", 0)
    retweets = metrics.get("retweet_count", 0)
    quotes = metrics.get("quote_count", 0)

    return likes + replies + retweets * 2 + quotes * 2


def post_url(post_id: str) -> str:
    return f"https://x.com/i/web/status/{post_id}"
```

Add `import requests_mock` to the top of `backend/tests/test_trends.py` if not already present from Task 4.

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v -k "trending or recent_posts or engagement or post_url"`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/trends.py backend/tests/test_trends.py
git commit -m "feat: add X (Twitter) trending topics and recent-search fetchers"
```

---

## Task 6: Instagram fetch functions

**Files:**
- Modify: `backend/app/trends.py`
- Modify: `backend/tests/test_trends.py`

**Interfaces:**
- Produces: `IG_ACCESS_TOKEN: str | None`, `IG_BUSINESS_ACCOUNT_ID: str | None`, `ig_find_hashtag_id(hashtag_name: str) -> str | None`, `ig_get_hashtag_media(hashtag_id: str, media_type: str = "top_media", limit: int = 25) -> list[dict]`, `search_instagram_hashtag(hashtag: str, media_type: str = "top_media", limit: int = 25) -> list[dict]`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_trends.py`:
```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v -k ig_`
Expected: FAIL — `ImportError: cannot import name 'ig_find_hashtag_id'`

- [ ] **Step 3: Implement Instagram functions**

Append to `backend/app/trends.py`:
```python
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
IG_BUSINESS_ACCOUNT_ID = os.getenv("IG_BUSINESS_ACCOUNT_ID")
GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


def ig_find_hashtag_id(hashtag_name: str) -> str | None:
    hashtag_name = hashtag_name.lstrip("#")

    url = f"{GRAPH_API_BASE}/ig_hashtag_search"
    params = {
        "user_id": IG_BUSINESS_ACCOUNT_ID,
        "q": hashtag_name,
        "access_token": IG_ACCESS_TOKEN,
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json().get("data", [])
    if not data:
        return None

    return data[0].get("id")


def ig_get_hashtag_media(hashtag_id: str, media_type: str = "top_media", limit: int = 25) -> list[dict]:
    url = f"{GRAPH_API_BASE}/{hashtag_id}/{media_type}"
    params = {
        "user_id": IG_BUSINESS_ACCOUNT_ID,
        "fields": "id,caption,like_count,comments_count,permalink,timestamp",
        "access_token": IG_ACCESS_TOKEN,
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    return response.json().get("data", [])[:limit]


def search_instagram_hashtag(hashtag: str, media_type: str = "top_media", limit: int = 25) -> list[dict]:
    hashtag_id = ig_find_hashtag_id(hashtag)
    if not hashtag_id:
        return []

    return ig_get_hashtag_media(hashtag_id, media_type=media_type, limit=limit)
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v -k ig_`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/trends.py backend/tests/test_trends.py
git commit -m "feat: add Instagram hashtag search fetchers"
```

---

## Task 7: Threads fetch function

**Files:**
- Modify: `backend/app/trends.py`
- Modify: `backend/tests/test_trends.py`

**Interfaces:**
- Produces: `THREADS_ACCESS_TOKEN: str | None`, `search_threads_keyword(keyword: str, limit: int = 25) -> list[dict]`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_trends.py`:
```python
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
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v -k threads`
Expected: FAIL — `ImportError: cannot import name 'search_threads_keyword'`

- [ ] **Step 3: Implement Threads function**

Append to `backend/app/trends.py`:
```python
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_API_BASE = "https://graph.threads.net/v1.0"


def search_threads_keyword(keyword: str, limit: int = 25) -> list[dict]:
    url = f"{THREADS_API_BASE}/keyword_search"
    params = {
        "q": keyword,
        "fields": "id,text,permalink,timestamp",
        "access_token": THREADS_ACCESS_TOKEN,
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    return response.json().get("data", [])[:limit]
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends.py -v -k threads`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/trends.py backend/tests/test_trends.py
git commit -m "feat: add Threads keyword search fetcher"
```

---

## Task 8: Row-building pipelines

**Files:**
- Modify: `backend/app/trends.py`
- Create: `backend/tests/test_trends_pipeline.py`

**Interfaces:**
- Consumes: everything from Tasks 1–7
- Produces: `build_x_rows(trend: str, base_link: str, campaign_name: str, posts_per_trend: int, output_posts_per_trend: int, use_ai_rewrite: bool) -> list[dict]`, `build_meta_rows(platform: str, query: str, base_link: str, campaign_name: str, posts_per_query: int, output_posts_per_query: int, use_ai_rewrite: bool) -> list[dict]`, `build_manual_rows(entries: list[dict], base_link: str, campaign_name: str, use_ai_rewrite: bool) -> list[dict]`

All three return lists of `TrendRow`-shaped dicts (keys listed in Task 3).

- [ ] **Step 1: Write failing tests**

`backend/tests/test_trends_pipeline.py`:
```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends_pipeline.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_x_rows'`

- [ ] **Step 3: Implement row-building pipelines**

Append to `backend/app/trends.py`:
```python
def _finalize_row(
    *,
    platform: str,
    trend: str,
    post_id: str,
    post_url_value: str,
    raw_text: str,
    likes: int,
    comments: int,
    retweets: int,
    quotes: int,
    engagement: int,
    created_at: str,
    keywords: list[str],
    base_link: str,
    campaign_name: str,
    use_ai_rewrite: bool,
    source: str,
) -> dict:
    hashtags = extract_hashtags(raw_text)
    tracked_link = build_tracked_link(base_link, campaign_name, trend, source=source)

    if use_ai_rewrite:
        rewritten_caption = rewrite_caption_with_claude(raw_text, trend, keywords)
    else:
        rewritten_caption = template_rewrite(trend, keywords)

    link_space = len(tracked_link) + 1
    max_caption_len = 280 - link_space
    caption = rewritten_caption
    if len(caption) > max_caption_len:
        caption = caption[: max_caption_len - 1].rstrip() + "…"
    buffer_text = f"{caption} {tracked_link}"

    tags = list(dict.fromkeys(keywords[:3] + [tag.lstrip("#") for tag in hashtags[:2]]))[:5]

    return {
        "platform": platform,
        "trend": trend,
        "post_id": post_id,
        "post_url": post_url_value,
        "original_text": raw_text,
        "keywords": keywords,
        "hashtags": hashtags,
        "likes": likes,
        "comments": comments,
        "retweets": retweets,
        "quotes": quotes,
        "engagement_score": engagement,
        "created_at": created_at,
        "tracked_link": tracked_link,
        "rewritten_caption": rewritten_caption,
        "buffer_text": buffer_text,
        "tags": tags,
    }


def build_x_rows(
    trend: str,
    base_link: str,
    campaign_name: str,
    posts_per_trend: int,
    output_posts_per_trend: int,
    use_ai_rewrite: bool,
) -> list[dict]:
    posts = search_recent_posts(trend, max_results=posts_per_trend)
    if not posts:
        return []

    trend_keywords = extract_tfidf_keywords([post.get("text", "") for post in posts], top_n=8)

    ranked_posts = sorted(posts, key=engagement_score, reverse=True)[:output_posts_per_trend]

    rows = []
    for post in ranked_posts:
        raw_text = post.get("text", "")
        metrics = post.get("public_metrics", {}) or {}
        keywords = trend_keywords or extract_simple_keywords(raw_text)

        rows.append(_finalize_row(
            platform="X",
            trend=trend,
            post_id=post.get("id", ""),
            post_url_value=post_url(post.get("id", "")),
            raw_text=raw_text,
            likes=metrics.get("like_count", 0),
            comments=metrics.get("reply_count", 0),
            retweets=metrics.get("retweet_count", 0),
            quotes=metrics.get("quote_count", 0),
            engagement=engagement_score(post),
            created_at=post.get("created_at", ""),
            keywords=keywords,
            base_link=base_link,
            campaign_name=campaign_name,
            use_ai_rewrite=use_ai_rewrite,
            source="twitter",
        ))

    return rows


def build_meta_rows(
    platform: str,
    query: str,
    base_link: str,
    campaign_name: str,
    posts_per_query: int,
    output_posts_per_query: int,
    use_ai_rewrite: bool,
) -> list[dict]:
    if platform == "Instagram":
        raw_posts = search_instagram_hashtag(query, limit=posts_per_query)
    elif platform == "Threads":
        raw_posts = search_threads_keyword(query, limit=posts_per_query)
    else:
        raise ValueError(f"Unsupported platform for API search: {platform}")

    if not raw_posts:
        return []

    normalized = []
    for post in raw_posts:
        text = post.get("caption") or post.get("text") or ""
        normalized.append({
            "id": post.get("id", ""),
            "text": text,
            "permalink": post.get("permalink", ""),
            "like_count": post.get("like_count", 0),
            "comments_count": post.get("comments_count", 0),
            "timestamp": post.get("timestamp", ""),
        })

    query_keywords = extract_tfidf_keywords([post["text"] for post in normalized], top_n=8)

    ranked_posts = sorted(
        normalized,
        key=lambda post: post["like_count"] + post["comments_count"] * 2,
        reverse=True,
    )[:output_posts_per_query]

    rows = []
    for post in ranked_posts:
        raw_text = post["text"]
        keywords = query_keywords or extract_simple_keywords(raw_text)

        rows.append(_finalize_row(
            platform=platform,
            trend=query,
            post_id=post["id"],
            post_url_value=post["permalink"],
            raw_text=raw_text,
            likes=post["like_count"],
            comments=post["comments_count"],
            retweets=0,
            quotes=0,
            engagement=post["like_count"] + post["comments_count"] * 2,
            created_at=post["timestamp"],
            keywords=keywords,
            base_link=base_link,
            campaign_name=campaign_name,
            use_ai_rewrite=use_ai_rewrite,
            source=platform.lower(),
        ))

    return rows


def build_manual_rows(
    entries: list[dict],
    base_link: str,
    campaign_name: str,
    use_ai_rewrite: bool,
) -> list[dict]:
    grouped_texts: dict[str, list[str]] = {}
    for entry in entries:
        grouped_texts.setdefault(entry["trend"], []).append(entry["text"])

    trend_keywords_cache = {
        trend: extract_tfidf_keywords(texts, top_n=8) for trend, texts in grouped_texts.items()
    }

    rows = []
    for entry in entries:
        trend = entry["trend"]
        platform = entry["platform"]
        raw_text = entry["text"]
        keywords = trend_keywords_cache.get(trend) or extract_simple_keywords(raw_text)

        rows.append(_finalize_row(
            platform=platform,
            trend=trend,
            post_id="",
            post_url_value="",
            raw_text=raw_text,
            likes=0,
            comments=0,
            retweets=0,
            quotes=0,
            engagement=0,
            created_at="",
            keywords=keywords,
            base_link=base_link,
            campaign_name=campaign_name,
            use_ai_rewrite=use_ai_rewrite,
            source=platform.lower(),
        ))

    return rows
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends_pipeline.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/trends.py backend/tests/test_trends_pipeline.py
git commit -m "feat: add row-building pipelines for X, Instagram/Threads, and manual paste"
```

---

## Task 9: `GET` trend-fetching routes

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_trends_routes.py`

**Interfaces:**
- Consumes: `build_x_rows`, `build_meta_rows`, `X_BEARER_TOKEN`, `IG_ACCESS_TOKEN`, `IG_BUSINESS_ACCOUNT_ID`, `THREADS_ACCESS_TOKEN` from `app.trends`; `get_trending_topics` from `app.trends`
- Produces: `TrendRow` Pydantic model, `GET /api/trends/x`, `GET /api/trends/x/search`, `GET /api/trends/instagram`, `GET /api/trends/threads` routes in `main.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_trends_routes.py`:
```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends_routes.py -v`
Expected: FAIL — 404s (routes don't exist yet)

- [ ] **Step 3: Add routes to `main.py`**

Add near the top of `backend/app/main.py`, after the existing imports:
```python
from app import trends
```

Add after the existing `VariationResponse` model definition:
```python
class TrendRow(BaseModel):
    platform: str
    trend: str
    post_id: str
    post_url: str
    original_text: str
    keywords: List[str]
    hashtags: List[str]
    likes: int
    comments: int
    retweets: int
    quotes: int
    engagement_score: int
    created_at: str
    tracked_link: str
    rewritten_caption: str
    buffer_text: str
    tags: List[str]
```

Add new routes (place after the existing `/api/health` route):
```python
@app.get("/api/trends/x", response_model=List[str])
def get_x_trending(woeid: str = "23424748", limit: int = 10) -> List[str]:
    if not trends.X_BEARER_TOKEN:
        raise HTTPException(status_code=503, detail="Missing X_BEARER_TOKEN")

    return trends.get_trending_topics(woeid=woeid, limit=limit)


@app.get("/api/trends/x/search", response_model=List[TrendRow])
def search_x_trends(
    query: str,
    base_link: str,
    campaign_name: str,
    max_results: int = 25,
    output_posts: int = 3,
    use_ai_rewrite: bool = True,
) -> List[TrendRow]:
    if not trends.X_BEARER_TOKEN:
        raise HTTPException(status_code=503, detail="Missing X_BEARER_TOKEN")

    return trends.build_x_rows(
        trend=query,
        base_link=base_link,
        campaign_name=campaign_name,
        posts_per_trend=max_results,
        output_posts_per_trend=output_posts,
        use_ai_rewrite=use_ai_rewrite,
    )


@app.get("/api/trends/instagram", response_model=List[TrendRow])
def search_instagram_trends(
    hashtag: str,
    base_link: str,
    campaign_name: str,
    max_results: int = 25,
    output_posts: int = 3,
    use_ai_rewrite: bool = True,
) -> List[TrendRow]:
    if not trends.IG_ACCESS_TOKEN or not trends.IG_BUSINESS_ACCOUNT_ID:
        raise HTTPException(status_code=503, detail="Missing IG_ACCESS_TOKEN or IG_BUSINESS_ACCOUNT_ID")

    return trends.build_meta_rows(
        platform="Instagram",
        query=hashtag,
        base_link=base_link,
        campaign_name=campaign_name,
        posts_per_query=max_results,
        output_posts_per_query=output_posts,
        use_ai_rewrite=use_ai_rewrite,
    )


@app.get("/api/trends/threads", response_model=List[TrendRow])
def search_threads_trends(
    keyword: str,
    base_link: str,
    campaign_name: str,
    max_results: int = 25,
    output_posts: int = 3,
    use_ai_rewrite: bool = True,
) -> List[TrendRow]:
    if not trends.THREADS_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="Missing THREADS_ACCESS_TOKEN")

    return trends.build_meta_rows(
        platform="Threads",
        query=keyword,
        base_link=base_link,
        campaign_name=campaign_name,
        posts_per_query=max_results,
        output_posts_per_query=output_posts,
        use_ai_rewrite=use_ai_rewrite,
    )
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends_routes.py -v`
Expected: 5 passed

- [ ] **Step 5: Add the new env vars to `.env.example`**

Append to `backend/.env.example`:
```
X_BEARER_TOKEN=
IG_ACCESS_TOKEN=
IG_BUSINESS_ACCOUNT_ID=
THREADS_ACCESS_TOKEN=
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_trends_routes.py backend/.env.example
git commit -m "feat: add X/Instagram/Threads trend-fetching routes"
```

---

## Task 10: Manual-paste route

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_trends_routes.py`

**Interfaces:**
- Consumes: `build_manual_rows` from `app.trends`
- Produces: `ManualEntry` Pydantic model, `POST /api/trends/manual`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_trends_routes.py`:
```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends_routes.py -v -k manual`
Expected: FAIL — 404 Not Found

- [ ] **Step 3: Add the route**

Add after the `TrendRow` model in `backend/app/main.py`:
```python
class ManualEntry(BaseModel):
    trend: str
    platform: str
    text: str


class ManualPasteRequest(BaseModel):
    base_link: str
    campaign_name: str
    use_ai_rewrite: bool = True
    entries: List[ManualEntry]
```

Add after the `/api/trends/threads` route:
```python
@app.post("/api/trends/manual", response_model=List[TrendRow])
def submit_manual_posts(payload: ManualPasteRequest) -> List[TrendRow]:
    if not payload.entries:
        return []

    return trends.build_manual_rows(
        entries=[entry.model_dump() for entry in payload.entries],
        base_link=payload.base_link,
        campaign_name=payload.campaign_name,
        use_ai_rewrite=payload.use_ai_rewrite,
    )
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends_routes.py -v -k manual`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_trends_routes.py
git commit -m "feat: add manual-paste trend submission route"
```

---

## Task 11: Video-prompt generation route

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_trends_routes.py`

**Interfaces:**
- Consumes: `rewrite_video_prompt_with_claude` from `app.trends`
- Produces: `VideoPromptRequest`/`VideoPromptResponse` Pydantic models, `POST /api/trends/video-prompt`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_trends_routes.py`:
```python
def test_video_prompt_returns_generated_prompt():
    with patch("app.main.trends.rewrite_video_prompt_with_claude", return_value="Cinematic shot of sneakers."):
        response = client.post("/api/trends/video-prompt", json={
            "trend": "#SneakerDrop",
            "keywords": ["sneakers", "limited edition"],
            "original_text": "New sneaker drop is everywhere",
        })
    assert response.status_code == 200
    assert response.json() == {"prompt": "Cinematic shot of sneakers."}
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends_routes.py -v -k video_prompt`
Expected: FAIL — 404 Not Found

- [ ] **Step 3: Add the route**

Add after `ManualPasteRequest` in `backend/app/main.py`:
```python
class VideoPromptRequest(BaseModel):
    trend: str
    keywords: List[str]
    original_text: str = ""


class VideoPromptResponse(BaseModel):
    prompt: str
```

Add after the `/api/trends/manual` route:
```python
@app.post("/api/trends/video-prompt", response_model=VideoPromptResponse)
def generate_video_prompt(payload: VideoPromptRequest) -> VideoPromptResponse:
    prompt = trends.rewrite_video_prompt_with_claude(
        original_text=payload.original_text,
        trend=payload.trend,
        keywords=payload.keywords,
    )
    return VideoPromptResponse(prompt=prompt)
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends_routes.py -v -k video_prompt`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_trends_routes.py
git commit -m "feat: add video-prompt generation route"
```

---

## Task 12: CSV export route

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_trends_routes.py`

**Interfaces:**
- Consumes: `make_buffer_csv`, `make_full_export_csv` from `app.trends`
- Produces: `ExportRequest` Pydantic model, `POST /api/trends/export`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_trends_routes.py`:
```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends_routes.py -v -k export`
Expected: FAIL — 404 Not Found

- [ ] **Step 3: Add the route**

Add after `VideoPromptResponse` in `backend/app/main.py`:
```python
from fastapi.responses import Response
from typing import Literal


class ExportRequest(BaseModel):
    rows: List[TrendRow]
    format: Literal["buffer", "full"]
    gap_minutes: int = 90
```

Add after the `/api/trends/video-prompt` route:
```python
@app.post("/api/trends/export")
def export_trend_rows(payload: ExportRequest) -> Response:
    row_dicts = [row.model_dump() for row in payload.rows]

    if payload.format == "buffer":
        csv_bytes = trends.make_buffer_csv(row_dicts, gap_minutes=payload.gap_minutes)
        filename = "buffer_bulk_upload.csv"
    else:
        csv_bytes = trends.make_full_export_csv(row_dicts)
        filename = "posts_full_export.csv"

    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && .venv/Scripts/pytest tests/test_trends_routes.py -v -k export`
Expected: 3 passed

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && .venv/Scripts/pytest -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_trends_routes.py
git commit -m "feat: add Buffer/full CSV export route"
```

---

## Task 13: Fix the Ark/Seedance task-submit + poll contract

**Files:**
- Modify: `backend/app/main.py:90-159` (the `create_variation` route and its Seedance call block)
- Create: `backend/tests/test_variations.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Produces: an async `call_seedance(prompt: str, style: str, source_video_url: str) -> str | None` helper in `main.py` that returns a downloadable video URL or `None`; `create_variation` calls it instead of the old inline block

- [ ] **Step 1: Write failing tests**

`backend/tests/test_variations.py`:
```python
import io

import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.main import app

client = TestClient(app)


def _upload_files():
    return {"video": ("clip.mp4", io.BytesIO(b"fake video bytes"), "video/mp4")}


@respx.mock
def test_create_variation_uses_task_submit_and_poll(monkeypatch):
    monkeypatch.setattr("app.main.SEEDANCE_API_KEY", "test-key")
    monkeypatch.setattr("app.main.SEEDANCE_API_URL", "https://ark.example/api/v3")

    create_route = respx.post("https://ark.example/api/v3/contents/generations/tasks").mock(
        return_value=Response(200, json={"id": "task-123"})
    )
    poll_route = respx.get("https://ark.example/api/v3/contents/generations/tasks/task-123").mock(
        return_value=Response(200, json={"status": "succeeded", "content": {"video_url": "https://cdn.example/out.mp4"}})
    )
    respx.get("https://cdn.example/out.mp4").mock(return_value=Response(200, content=b"generated video bytes"))

    response = client.post(
        "/api/variations",
        data={"prompt": "Cinematic showcase", "style": "Cinematic"},
        files=_upload_files(),
    )

    assert response.status_code == 200
    body = response.json()
    assert "Generated with Seedance" in " ".join(body["notes"])
    assert create_route.called
    assert poll_route.called


@respx.mock
def test_create_variation_falls_back_when_task_fails(monkeypatch):
    monkeypatch.setattr("app.main.SEEDANCE_API_KEY", "test-key")
    monkeypatch.setattr("app.main.SEEDANCE_API_URL", "https://ark.example/api/v3")

    respx.post("https://ark.example/api/v3/contents/generations/tasks").mock(
        return_value=Response(200, json={"id": "task-123"})
    )
    respx.get("https://ark.example/api/v3/contents/generations/tasks/task-123").mock(
        return_value=Response(200, json={"status": "failed", "error": {"message": "bad prompt"}})
    )

    response = client.post(
        "/api/variations",
        data={"prompt": "Cinematic showcase", "style": "Cinematic"},
        files=_upload_files(),
    )

    assert response.status_code == 200
    body = response.json()
    assert any("failed" in note.lower() or "fallback" in note.lower() for note in body["notes"])


def test_create_variation_skips_seedance_when_no_key(monkeypatch):
    monkeypatch.setattr("app.main.SEEDANCE_API_KEY", "")

    response = client.post(
        "/api/variations",
        data={"prompt": "Cinematic showcase", "style": "Cinematic"},
        files=_upload_files(),
    )

    assert response.status_code == 200
    body = response.json()
    assert not any("Seedance" in note for note in body["notes"])
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && .venv/Scripts/pytest tests/test_variations.py -v`
Expected: FAIL — with the old implementation, no request is ever made to `.../contents/generations/tasks`, so `create_route`/`poll_route` are never called and `respx` raises an unmocked-request error for the old multipart POST target.

- [ ] **Step 3: Replace the Seedance call block**

In `backend/app/main.py`, replace the block from `if SEEDANCE_API_KEY:` through the matching `except Exception as exc:` (originally lines 108-127) with a call to a new helper, and define that helper above `create_variation`:

```python
import asyncio


async def call_seedance(prompt: str, style: str, source_video_url: str) -> str | None:
    async with httpx.AsyncClient(timeout=30) as client:
        create_response = await client.post(
            f"{SEEDANCE_API_URL}/contents/generations/tasks",
            headers={"Authorization": f"Bearer {SEEDANCE_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "doubao-seedance-2-0-260128",
                "content": [
                    {"type": "text", "text": f"{prompt} (style: {style})"},
                    {"type": "video_url", "video_url": {"url": source_video_url}},
                ],
            },
        )
        create_response.raise_for_status()
        task_id = create_response.json()["id"]

        poll_url = f"{SEEDANCE_API_URL}/contents/generations/tasks/{task_id}"
        headers = {"Authorization": f"Bearer {SEEDANCE_API_KEY}"}

        for _attempt in range(40):
            poll_response = await client.get(poll_url, headers=headers)
            poll_response.raise_for_status()
            payload = poll_response.json()
            status = payload.get("status")

            if status == "succeeded":
                return payload.get("content", {}).get("video_url")
            if status == "failed":
                error_message = payload.get("error", {}).get("message", "unknown error")
                raise RuntimeError(f"Seedance task failed: {error_message}")

            await asyncio.sleep(3)

        raise TimeoutError("Seedance task did not complete in time")
```

Then update `create_variation` to call it in place of the old inline block:
```python
    if SEEDANCE_API_KEY:
        try:
            remote_url = await call_seedance(prompt=prompt, style=style or "Cinematic", source_video_url=original_url)
            if remote_url:
                async with httpx.AsyncClient(timeout=120) as client:
                    download = await client.get(remote_url)
                    download.raise_for_status()
                    output_path.write_bytes(download.content)
                    notes.append("Generated with Seedance2.0 API")
            else:
                raise HTTPException(status_code=502, detail="Seedance API response missing output URL")
        except Exception as exc:
            notes.append(f"Seedance call failed, fallback preview created: {exc}")
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && .venv/Scripts/pytest tests/test_variations.py -v`
Expected: 3 passed

- [ ] **Step 5: Update `.env.example` with a note about model id**

In `backend/.env.example`, add a comment above `SEEDANCE_API_URL`:
```
# SEEDANCE_API_URL is the Ark base URL only, e.g. https://ark.ap-southeast.bytepluses.com/api/v3
# (the /contents/generations/tasks path is appended by the backend)
```

- [ ] **Step 6: Run the full backend test suite**

Run: `cd backend && .venv/Scripts/pytest -v`
Expected: all tests pass

- [ ] **Step 7: Manual smoke test against the real Ark endpoint**

With real `SEEDANCE_API_KEY`/`SEEDANCE_API_URL` set in `backend/.env`, start the backend (`cd backend && .venv/Scripts/uvicorn app.main:app --reload`) and submit a real video through `POST /api/variations` (via curl, the frontend, or `/docs`). Confirm in the response notes whether it says `"Generated with Seedance2.0 API"` (success) or a fallback message with the real error text. If the model id or the `video_url` content-type field name is rejected by the live API, adjust `call_seedance`'s `model` value and content-type field to match the actual error message from Ark, then re-run this step.

- [ ] **Step 8: Commit**

```bash
git add backend/app/main.py backend/tests/test_variations.py backend/.env.example
git commit -m "fix: use Ark's real async task-submit/poll contract for Seedance calls"
```

---

## Task 14: Frontend — Trends section scaffold with X search

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `GET /api/trends/x/search` from Task 9
- Produces: a `TrendsSection` block inside `App.jsx` with `trendSource`, `trendRows`, `trendLoading`, `trendError`, `baseLinkInput`, `campaignNameInput` state, wired for the "X search" source only (other sources added in Task 15)

- [ ] **Step 1: Add nav link and section state**

In `frontend/src/App.jsx`, add `Trends` to the nav links (inside `<div className="nav-links">`, after `Workflow`):
```jsx
<a href={`${PUBLIC_BASE}#trends`}>Trends</a>
```

Add new state inside `function App()`, alongside the existing state declarations:
```jsx
const [trendSource, setTrendSource] = useState('x-search');
const [xQuery, setXQuery] = useState('#AI');
const [baseLinkInput, setBaseLinkInput] = useState('https://yourdomain.com/blog');
const [campaignNameInput, setCampaignNameInput] = useState('trend_roundup');
const [trendRows, setTrendRows] = useState([]);
const [trendLoading, setTrendLoading] = useState(false);
const [trendError, setTrendError] = useState('');
```

- [ ] **Step 2: Add the fetch handler**

Add inside `function App()`, near `handleSubmit`:
```jsx
const handleFetchTrends = async (event) => {
  event.preventDefault();
  setTrendLoading(true);
  setTrendError('');

  try {
    const params = new URLSearchParams({
      query: xQuery,
      base_link: baseLinkInput,
      campaign_name: campaignNameInput,
    });
    const response = await fetch(apiUrl(`/api/trends/x/search?${params.toString()}`));

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || 'Could not fetch trends.');
    }

    const data = await response.json();
    setTrendRows(data);
  } catch (err) {
    setTrendError(err.message || 'Something went wrong.');
  } finally {
    setTrendLoading(false);
  }
};
```

- [ ] **Step 3: Add the Trends section JSX**

Add a new `<section className="trends-section" id="trends">` between the `workflow-panel` section and the `generator-section` in the returned JSX:
```jsx
<section className="trends-section" id="trends">
  <div className="section-heading split">
    <div>
      <p className="eyebrow">Trends</p>
      <h2>Pull a prompt from what's trending right now.</h2>
    </div>
    <p className="section-text">
      Fetch trending posts, then send one straight into the Generator as a
      video prompt.
    </p>
  </div>

  <form className="trends-form" onSubmit={handleFetchTrends}>
    <label>
      Source
      <select value={trendSource} onChange={(e) => setTrendSource(e.target.value)}>
        <option value="x-search">X search</option>
      </select>
    </label>
    <label>
      Search query / hashtag
      <input type="text" value={xQuery} onChange={(e) => setXQuery(e.target.value)} />
    </label>
    <label>
      Base link
      <input type="text" value={baseLinkInput} onChange={(e) => setBaseLinkInput(e.target.value)} />
    </label>
    <label>
      Campaign name
      <input type="text" value={campaignNameInput} onChange={(e) => setCampaignNameInput(e.target.value)} />
    </label>
    <button className="primary-btn" type="submit" disabled={trendLoading}>
      {trendLoading ? 'Fetching...' : 'Fetch trends'}
    </button>
    {trendError && <p className="error-text">{trendError}</p>}
  </form>

  {trendRows.length > 0 && (
    <table className="trends-table">
      <thead>
        <tr>
          <th>Platform</th>
          <th>Trend</th>
          <th>Keywords</th>
          <th>Engagement</th>
          <th>Original text</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {trendRows.map((row) => (
          <tr key={`${row.platform}-${row.post_id}-${row.trend}`}>
            <td>{row.platform}</td>
            <td>{row.trend}</td>
            <td>{row.keywords.join(', ')}</td>
            <td>{row.engagement_score}</td>
            <td>{row.original_text}</td>
            <td></td>
          </tr>
        ))}
      </tbody>
    </table>
  )}
</section>
```

- [ ] **Step 4: Add minimal styles**

Append to `frontend/src/styles.css`:
```css
.trends-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  align-items: end;
  margin-bottom: 2rem;
}

.trends-table {
  width: 100%;
  border-collapse: collapse;
}

.trends-table th,
.trends-table td {
  text-align: left;
  padding: 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  vertical-align: top;
}
```

- [ ] **Step 5: Manually verify**

Run: `cd backend && .venv/Scripts/uvicorn app.main:app --reload` (in one terminal) and `cd frontend && npm run dev` (in another). With a real `X_BEARER_TOKEN` set in `backend/.env`, open the dev server URL, click "Trends" in the nav, enter a query, click "Fetch trends", and confirm the results table populates. Without a token set, confirm the error message from the `503` response is shown instead of a crash.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.jsx frontend/src/styles.css
git commit -m "feat: add Trends section with X search to the frontend"
```

---

## Task 15: Frontend — Instagram, Threads, and manual-paste sources

**Files:**
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `GET /api/trends/instagram`, `GET /api/trends/threads`, `POST /api/trends/manual` from Tasks 9–10
- Produces: extends `trendSource` handling to `instagram`, `threads`, and `manual`; adds `manualQueue`, `igHashtagsQueried` state

- [ ] **Step 1: Extend source state and add manual-paste queue state**

Add alongside the Task 14 state:
```jsx
const [igHashtag, setIgHashtag] = useState('sustainablefashion');
const [threadsKeyword, setThreadsKeyword] = useState('sustainable fashion');
const [pasteTrend, setPasteTrend] = useState('');
const [pastePlatform, setPastePlatform] = useState('X');
const [pasteBlock, setPasteBlock] = useState('');
const [manualQueue, setManualQueue] = useState([]);
const [igHashtagsQueried, setIgHashtagsQueried] = useState(new Set());
```

- [ ] **Step 2: Extend `handleFetchTrends` for all sources**

Replace the body of `handleFetchTrends` from Task 14 with:
```jsx
const handleFetchTrends = async (event) => {
  event.preventDefault();
  setTrendLoading(true);
  setTrendError('');

  try {
    if (trendSource === 'manual') {
      if (manualQueue.length === 0) {
        throw new Error('Add at least one pasted post before submitting.');
      }
      const response = await fetch(apiUrl('/api/trends/manual'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_link: baseLinkInput,
          campaign_name: campaignNameInput,
          use_ai_rewrite: true,
          entries: manualQueue,
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || 'Could not submit pasted posts.');
      }
      setTrendRows(await response.json());
      return;
    }

    let path;
    const params = new URLSearchParams({ base_link: baseLinkInput, campaign_name: campaignNameInput });

    if (trendSource === 'x-search') {
      params.set('query', xQuery);
      path = `/api/trends/x/search?${params.toString()}`;
    } else if (trendSource === 'instagram') {
      params.set('hashtag', igHashtag);
      path = `/api/trends/instagram?${params.toString()}`;
    } else {
      params.set('keyword', threadsKeyword);
      path = `/api/trends/threads?${params.toString()}`;
    }

    const response = await fetch(apiUrl(path));
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || 'Could not fetch trends.');
    }
    const data = await response.json();
    setTrendRows(data);

    if (trendSource === 'instagram') {
      setIgHashtagsQueried((prev) => new Set([...prev, igHashtag.replace(/^#/, '')]));
    }
  } catch (err) {
    setTrendError(err.message || 'Something went wrong.');
  } finally {
    setTrendLoading(false);
  }
};

const handleAddToQueue = (event) => {
  event.preventDefault();
  const posts = pasteBlock.includes('---')
    ? pasteBlock.split('---').map((chunk) => chunk.trim()).filter(Boolean)
    : pasteBlock.split('\n').map((line) => line.trim()).filter(Boolean);

  if (!pasteTrend.trim() || posts.length === 0) return;

  setManualQueue((prev) => [
    ...prev,
    ...posts.map((text) => ({ trend: pasteTrend.trim(), platform: pastePlatform, text })),
  ]);
  setPasteBlock('');
};
```

- [ ] **Step 3: Extend the source `<select>` and add per-source inputs**

Replace the `<select>` from Task 14 with:
```jsx
<select value={trendSource} onChange={(e) => setTrendSource(e.target.value)}>
  <option value="x-search">X search</option>
  <option value="instagram">Instagram hashtag</option>
  <option value="threads">Threads keyword</option>
  <option value="manual">Paste manually</option>
</select>
```

Replace the single "Search query / hashtag" `<label>` from Task 14 with conditional inputs:
```jsx
{trendSource === 'x-search' && (
  <label>
    Search query / hashtag
    <input type="text" value={xQuery} onChange={(e) => setXQuery(e.target.value)} />
  </label>
)}
{trendSource === 'instagram' && (
  <label>
    Instagram hashtag
    <input type="text" value={igHashtag} onChange={(e) => setIgHashtag(e.target.value)} />
    <span className="hint">{igHashtagsQueried.size} / 30 hashtags used this window</span>
  </label>
)}
{trendSource === 'threads' && (
  <label>
    Threads keyword
    <input type="text" value={threadsKeyword} onChange={(e) => setThreadsKeyword(e.target.value)} />
  </label>
)}
```

Add a manual-paste block, rendered only when `trendSource === 'manual'`, directly after the form's closing `</form>` tag (still inside the section):
```jsx
{trendSource === 'manual' && (
  <div className="manual-paste-panel">
    <label>
      Topic / trend label
      <input type="text" value={pasteTrend} onChange={(e) => setPasteTrend(e.target.value)} />
    </label>
    <label>
      Platform
      <select value={pastePlatform} onChange={(e) => setPastePlatform(e.target.value)}>
        <option>X</option>
        <option>Instagram</option>
        <option>Threads</option>
        <option>Facebook</option>
        <option>Other</option>
      </select>
    </label>
    <label>
      Paste post captions (one per line, or separate multi-line posts with a line containing only ---)
      <textarea value={pasteBlock} onChange={(e) => setPasteBlock(e.target.value)} rows="4" />
    </label>
    <button className="ghost-btn" type="button" onClick={handleAddToQueue}>Add to queue</button>
    <p className="hint">{manualQueue.length} post(s) queued</p>
  </div>
)}
```

- [ ] **Step 4: Manually verify**

With `IG_ACCESS_TOKEN`/`IG_BUSINESS_ACCOUNT_ID` or `THREADS_ACCESS_TOKEN` set (or unset, to check the `503` error path), exercise each source in the dev server: Instagram hashtag search, Threads keyword search, and paste-manually (add two posts to the queue, submit, confirm rows appear).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: add Instagram, Threads, and manual-paste sources to Trends section"
```

---

## Task 16: Frontend — "Use for video" and CSV export

**Files:**
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `POST /api/trends/video-prompt` (Task 11), `POST /api/trends/export` (Task 12), existing `prompt`/`setPrompt` state from the Generator section
- Produces: a working "Use for video" button per row and two CSV download buttons

- [ ] **Step 1: Add the "Use for video" handler**

Add inside `function App()`:
```jsx
const handleUseForVideo = async (row) => {
  try {
    const response = await fetch(apiUrl('/api/trends/video-prompt'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trend: row.trend,
        keywords: row.keywords,
        original_text: row.original_text,
      }),
    });
    if (!response.ok) return;
    const data = await response.json();
    setPrompt(data.prompt);
    document.getElementById('generator')?.scrollIntoView({ behavior: 'smooth' });
  } catch {
    // no-op: leave the existing prompt untouched on failure
  }
};

const handleExportTrends = async (format) => {
  const response = await fetch(apiUrl('/api/trends/export'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows: trendRows, format, gap_minutes: 90 }),
  });
  if (!response.ok) return;

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = format === 'buffer' ? 'buffer_bulk_upload.csv' : 'posts_full_export.csv';
  link.click();
  URL.revokeObjectURL(url);
};
```

- [ ] **Step 2: Wire the "Use for video" button into the results table**

Replace the empty `<td></td>` at the end of each row (from Task 14) with:
```jsx
<td>
  <button className="ghost-btn" type="button" onClick={() => handleUseForVideo(row)}>
    Use for video
  </button>
</td>
```

- [ ] **Step 3: Add CSV export buttons below the table**

Add directly after the closing `</table>` tag, still inside the `trendRows.length > 0 && (...)` block:
```jsx
<div className="trends-export-actions">
  <button className="ghost-btn" type="button" onClick={() => handleExportTrends('buffer')}>
    Download Buffer CSV
  </button>
  <button className="ghost-btn" type="button" onClick={() => handleExportTrends('full')}>
    Download full CSV
  </button>
</div>
```

- [ ] **Step 4: Manually verify end-to-end**

With the backend and frontend dev servers running and a real `X_BEARER_TOKEN` (or Instagram/Threads tokens, or the paste mode) configured: fetch trends, click "Use for video" on a row, confirm the page scrolls to Generator and the prompt field is populated with generated text, confirm it's editable, then upload a test video and click "Generate variation" to confirm the full pipeline runs (using the Ark fix from Task 13). Also click both CSV download buttons and confirm files download with the expected columns.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: wire trend rows to video-prompt generation and CSV export"
```

---

## Final check

- [ ] Run `cd backend && .venv/Scripts/pytest -v` — all backend tests pass.
- [ ] Run `cd frontend && npm run build` — frontend builds with no errors.
- [ ] Confirm `backend/.env.example` lists all new variables: `X_BEARER_TOKEN`, `ANTHROPIC_API_KEY`, `IG_ACCESS_TOKEN`, `IG_BUSINESS_ACCOUNT_ID`, `THREADS_ACCESS_TOKEN`.
