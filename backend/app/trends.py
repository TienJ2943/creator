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
