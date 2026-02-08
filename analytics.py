import json
import os
from collections import Counter, defaultdict
from threading import Lock

from content_filter import visible_text_from_html, tokenize_text

UNIQUE_URLS = set()

LONGEST_URL = None
LONGEST_WORD_COUNT = 0

WORD_FREQ = Counter()

SUBDOMAIN_PAGES = defaultdict(set)

_ANALYTICS_LOCK = Lock()


def remove_fragment(url: str) -> str:
    return url.split("#", 1)[0]


def extract_host(url: str) -> str:
    if "://" in url:
        url = url.split("://", 1)[1]
    host = url.split("/", 1)[0]
    host = host.split(":", 1)[0]
    return host.lower()


def record_page(url: str, html: str) -> None:
    """
    Call once per downloaded HTML page.
    Uses stopwords via content_filter.tokenize_text().
    Thread-safe updates of globals.
    """
    global LONGEST_URL, LONGEST_WORD_COUNT

    if not url or not html:
        return

    clean_url = remove_fragment(url)
    host = extract_host(clean_url)

    # expensive parsing/tokenizing outside the lock
    try:
        text = visible_text_from_html(html)   # parses HTML internally
        tokens = tokenize_text(text)          # stopwords removed here
    except Exception:
        return

    wc = len(tokens)

    with _ANALYTICS_LOCK:
        UNIQUE_URLS.add(clean_url)

        if host.endswith("uci.edu"):
            SUBDOMAIN_PAGES[host].add(clean_url)

        if wc > LONGEST_WORD_COUNT:
            LONGEST_WORD_COUNT = wc
            LONGEST_URL = clean_url

        WORD_FREQ.update(tokens)


def write_report(path: str = "report.json") -> None:
    with _ANALYTICS_LOCK:
        state = {
            "unique_urls": list(UNIQUE_URLS),
            "longest_page": {"url": LONGEST_URL, "word_count": LONGEST_WORD_COUNT},
            "word_freq": dict(WORD_FREQ),
            "subdomain_pages": {k: list(v) for k, v in SUBDOMAIN_PAGES.items()},
        }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)


def load_report(path: str = "report.json") -> None:
    global UNIQUE_URLS, LONGEST_URL, LONGEST_WORD_COUNT, WORD_FREQ, SUBDOMAIN_PAGES

    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)

    new_unique = set(state.get("unique_urls", []))

    lp = state.get("longest_page", {})
    new_longest_url = lp.get("url", None)
    new_longest_wc = int(lp.get("word_count", 0) or 0)

    new_word_freq = Counter(state.get("word_freq", {}))

    sd = state.get("subdomain_pages", {})
    new_subdomains = defaultdict(set)
    for sub, urls in sd.items():
        new_subdomains[sub] = set(urls)

    with _ANALYTICS_LOCK:
        UNIQUE_URLS = new_unique
        LONGEST_URL = new_longest_url
        LONGEST_WORD_COUNT = new_longest_wc
        WORD_FREQ = new_word_freq
        SUBDOMAIN_PAGES = new_subdomains
