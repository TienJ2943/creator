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
