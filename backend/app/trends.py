import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd


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
        # image_url is always empty by design: no per-platform media-URL
        # extraction is implemented, so this column ships blank for every row.
        # Buffer's CSV format still expects an "Image URL" column to exist
        # (media can be attached separately in Buffer), so we keep it rather
        # than drop it.
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
