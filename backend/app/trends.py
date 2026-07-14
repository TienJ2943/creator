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
