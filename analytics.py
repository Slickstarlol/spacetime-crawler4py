from collections import Counter, defaultdict
import content_filter

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
    text = content_filter.visible_text_from_html(html)
    tokens = content_filter.tokenize_text(text)

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


def write_report(path: str = "report.txt") -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"Unique pages: {unique_page_count()}\n\n")

        url, wc = longest_page()
        f.write("Longest page (by word count):\n")
        f.write(f"{url}, {wc}\n\n")

        f.write("Top 50 words:\n")
        for word, count in top_words(50):
            f.write(f"{word}, {count}\n")
        f.write("\n")

        f.write("Subdomains under uci.edu:\n")
        for sub, count in subdomain_report():
            f.write(f"{sub}, {count}\n")
