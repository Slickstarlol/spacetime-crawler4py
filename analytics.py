import json
import os
from collections import Counter, defaultdict
from content_filter import visible_text_from_html, tokenize_text

# Global variables

UNIQUE_URLS = set()

LONGEST_URL = None
LONGEST_WORD_COUNT = 0

WORD_FREQ = Counter()

SUBDOMAIN_PAGES = defaultdict(set)



def remove_fragment(url: str) -> str:
    """Remove #fragment from URL."""
    return url.split("#", 1)[0]


def extract_host(url: str) -> str:
    """
    Extract hostname from URL using string operations only.
    Examples:
      https://www.ics.uci.edu/path -> www.ics.uci.edu
      http://ics.uci.edu:8080/ -> ics.uci.edu
    """
    if "://" in url:
        url = url.split("://", 1)[1]

    # remove path
    host = url.split("/", 1)[0]

    # remove port
    host = host.split(":", 1)[0]

    return host.lower()


def record_page(url: str, html: str) -> None:
    """
    Call ONCE per successfully downloaded page.
    Updates all analytics without affecting crawling.
    """
    global LONGEST_URL, LONGEST_WORD_COUNT

    if not url:
        return

    clean_url = remove_fragment(url)

    # 1) Unique pages (URL-based only)
    UNIQUE_URLS.add(clean_url)

    # 4) Subdomains under uci.edu
    host = extract_host(clean_url)
    if host.endswith("uci.edu"):
        SUBDOMAIN_PAGES[host].add(clean_url)

    # HTML -> visible text -> tokens
    text = visible_text_from_html(html)
    tokens = tokenize_text(text)

    # 2) Longest page
    wc = len(tokens)
    if wc > LONGEST_WORD_COUNT:
        LONGEST_WORD_COUNT = wc
        LONGEST_URL = clean_url

    # 3) Word frequencies
    WORD_FREQ.update(tokens)

# To get reports

def unique_page_count() -> int:
    return len(UNIQUE_URLS)


def longest_page():
    return LONGEST_URL, LONGEST_WORD_COUNT


def top_words(n: int = 50):
    return WORD_FREQ.most_common(n)


def subdomain_report():
    """
    Returns sorted list of (subdomain, count)
    """
    return sorted(
        ((sub, len(urls)) for sub, urls in SUBDOMAIN_PAGES.items()),
        key=lambda x: x[0]
    )


def write_report(path: str = "report.json") -> None:
    """
    Serializes the global crawler state to a JSON file.
    Converts sets to lists to ensure JSON compatibility.
    """
    # Create a dictionary representation of the global state
    state = {
        "unique_urls": list(UNIQUE_URLS),
        "longest_page": {
            "url": LONGEST_URL,
            "word_count": LONGEST_WORD_COUNT
        },
        "word_freq": dict(WORD_FREQ),  # Convert Counter to standard dict
        # Convert defaultdict(set) to dict(list)
        "subdomain_pages": {k: list(v) for k, v in SUBDOMAIN_PAGES.items()}
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
        print(f"Report saved to {path}")
    except Exception as e:
        print(f"Failed to save report: {e}")

def load_report(path: str = "report.json") -> None:
    """
    Loads the JSON report file if it exists and populates the global variables.
    Converts lists back into sets and dictionaries back into Counters.
    """
    global UNIQUE_URLS, LONGEST_URL, LONGEST_WORD_COUNT, WORD_FREQ, SUBDOMAIN_PAGES

    if not os.path.exists(path):
        print(f"No previous state found at {path}. Starting fresh.")
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        # 1. Restore Unique URLs (List -> Set)
        UNIQUE_URLS = set(state.get("unique_urls", []))

        # 2. Restore Longest Page
        longest_page_data = state.get("longest_page", {})
        LONGEST_URL = longest_page_data.get("url", None)
        LONGEST_WORD_COUNT = longest_page_data.get("word_count", 0)

        # 3. Restore Word Frequency 
        WORD_FREQ = Counter(state.get("word_freq", {}))

        # 4. Restore Subdomain Pages
        subdomain_data = state.get("subdomain_pages", {})
        SUBDOMAIN_PAGES = defaultdict(set)
        for subdomain, urls in subdomain_data.items():
            SUBDOMAIN_PAGES[subdomain] = set(urls)

        print(f"Successfully loaded state from {path}")
        print(f"Resuming with {len(UNIQUE_URLS)} unique pages and {len(WORD_FREQ)} words.")

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Error loading report file: {e}. Starting fresh to prevent corruption.")