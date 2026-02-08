import re
import hashlib
from collections import Counter
from bs4 import BeautifulSoup
from threading import Lock

# Hash maps
SEEN_CONTENT_HASHES = set()   # exact duplicates
SEEN_SIMHASHES = set()        # near duplicates

# One lock for all shared state in this module
_CF_LOCK = Lock()

# Stop word filtering
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't",
    "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself",
    "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into",
    "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "oursourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's",
    "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs",
    "them", "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's",
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't",
    "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself",
    "yourselves"
}


# Extract readable text
def visible_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def tokenize_text(text: str, *, min_len: int = 3, remove_stopwords: bool = True) -> list[str]:
    # Iterator to create individual tokens
    def iter_tokens_from_text():
        token_chars = []
        for ch in text:
            if not ch.isascii():
                if token_chars:
                    yield "".join(token_chars).lower()
                    token_chars.clear()
                continue

            if ch.isalnum():
                token_chars.append(ch)
            else:
                if token_chars:
                    yield "".join(token_chars).lower()
                    token_chars.clear()

        if token_chars:
            yield "".join(token_chars).lower()

    tokens = []
    for tok in iter_tokens_from_text():
        if len(tok) < min_len:
            continue
        if remove_stopwords and tok in STOP_WORDS:
            continue
        tokens.append(tok)
    return tokens


# For exact duplicate pages using CheckSum
def content_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


# For near duplicate pages using hashing
def _hash64(token: str) -> int:
    d = hashlib.sha1(token.encode("utf-8", errors="ignore")).digest()
    return int.from_bytes(d[:8], "big", signed=False)

def simhash(tokens: list[str]) -> int:
    counts = Counter(tokens)
    v = [0] * 64
    for tok, w in counts.items():
        h = _hash64(tok)
        for i in range(64):
            v[i] += w if ((h >> i) & 1) else -w

    out = 0
    for i in range(64):
        if v[i] > 0:
            out |= (1 << i)
    return out

def hamming_distance64(a: int, b: int) -> int:
    return (a ^ b).bit_count()

def is_near_duplicate(sh: int, *, threshold: int = 4) -> bool:
    # NOTE: caller must hold _CF_LOCK if you want this to be consistent
    for prev in SEEN_SIMHASHES:
        if hamming_distance64(sh, prev) <= threshold:
            return True
    return False

# For low-information webpages
def is_low_information(text: str, tokens: list[str]) -> bool:
    if len(tokens) < 40:
        return True

    # Check for reptition
    counts = Counter(tokens)
    most_common = counts.most_common(1)[0][1]
    if most_common / max(1, len(tokens)) > 0.25:
        return True

    # Check for vocabulary usage
    unique_ratio = len(counts) / max(1, len(tokens))
    if unique_ratio < 0.12:
        return True

    return False

def should_expand_page(html: str, url, *, simhash_threshold: int = 4) -> bool:
    """
    Returns False if thin / duplicate / near-duplicate.
    Thread-safe updates of seen sets.
    """
    text = visible_text_from_html(html)
    tokens = tokenize_text(text)

    if is_low_information(text, tokens):
        return False

    ch = content_checksum(text)
    sh = simhash(tokens)

    # Atomic check+add
    with _CF_LOCK:
        if ch in SEEN_CONTENT_HASHES:
            return False
        if is_near_duplicate(sh, threshold=simhash_threshold):
            return False

        SEEN_CONTENT_HASHES.add(ch)
        SEEN_SIMHASHES.add(sh)

    return True
