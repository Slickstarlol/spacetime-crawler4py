import re
import hashlib
from collections import Counter
from bs4 import BeautifulSoup

# Hash maps
SEEN_CONTENT_HASHES = set()   # For exact duplicate
SEEN_SIMHASHES = set()        # For near duplicate


# Stop word filtering
STOP_WORDS = {
    "about", "above", "after", "again", "against","aren't", "because", "been", 
    "before", "being", "below", "between", "both", "can't", "cannot", "could", 
    "couldn't", "didn't", "does", "doesn't", "doing", "don't", "down", "during", 
    "each", "from", "further","hadn't", "hasn't", "have", "haven't", "having", 
    "he'd", "he'll", "here", "here's", "hers", "herself", "himself", "how's", 
    "i'll", "i've", "into", "isn't", "it's", "itself", "let's", "more", "most", 
    "mustn't", "myself", "once", "only", "other", "ought", "oursourselves", 
    "over", "same", "shan't", "she'd", "she'll", "she's", "should", "shouldn't", 
    "some", "such", "than", "that", "that's", "their", "theirs", "them", 
    "themselves", "then", "there", "there's", "these", "they", "they'd", 
    "they'll", "they're", "they've", "this", "those", "through", "under", 
    "until", "very", "wasn't", "we'd", "we'll", "we're", "we've", "were", 
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which", 
    "while", "who's", "whom", "why's", "with", "won't", "would", "wouldn't", 
    "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
}


# Extract readable text
def visible_text_from_html(soup: BeautifulSoup) -> str:
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
    for prev in SEEN_SIMHASHES:
        if hamming_distance64(sh, prev) <= threshold:
            return True
    return False

# For low-information webpages
def is_low_information(text: str, tokens: list[str]) -> bool:
    # 
    ''' Contemplating whether to restrict text count, due to menu pages
    if len(text) < 200:
        return True
    '''
    if len(tokens) < 80:
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
    

# Combine all filters to check web-pages
def should_expand_page(soup: BeautifulSoup, url, *, simhash_threshold: int = 4) -> bool:
    """
    Returns False if the page is thin / duplicate / near-duplicate.
    Updates global seen-sets when the page is accepted.
    """
    text = visible_text_from_html(soup)
    tokens = tokenize_text(text)

    if is_low_information(text, tokens):
        return False

    ch = content_checksum(text)
    if ch in SEEN_CONTENT_HASHES:
        #print(f"CF;Duplicate detected: {url}")						    					# DEBUGGING
        return False
    SEEN_CONTENT_HASHES.add(ch)

    sh = simhash(tokens)
    if is_near_duplicate(sh, threshold=simhash_threshold):
        #print(f"CF;Near-duplicate detected: {url}")											# DEBUGGING
        return False
    SEEN_SIMHASHES.add(sh)

    return True
