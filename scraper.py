import re
from urllib.parse import urlparse, urljoin, urldefrag
from bs4 import BeautifulSoup
import content_filter

MAX_PAGE_SIZE = 10 * 1024 * 1024    # 10 MB
MIN_PAGE_SIZE = 100                 # 100 bytes

MAX_PATH_DEPTH = 10

MAX_QUERY_LEN = 5

BAD_EXTENSIONS_REGEX = (r".*\.(css|js|bmp|gif|jpe?g|ico"
                        + r"|png|tiff?|mid|mp2|mp3|mp4"
                        + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
                        + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
                        + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
                        + r"|epub|dll|cnf|tgz|sha1"
                        + r"|thmx|mso|arff|rtf|jar|csv|txt|odc|sas"
                        + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$")



def scraper(url: str, resp):
    # Validate response
    if resp.status != 200 or not resp or not resp.raw_response:
        return list()

    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp) -> list[str]:
    """
    url: the URL that was used to get the page
    resp.url: the actual url of the page
    resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    resp.error: when status is not 200, you can check the error here, if needed.
    resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
        resp.raw_response.url: the url, again
        resp.raw_response.content: the content of the page!
    Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    """

    links = set()

    try:
        # Decode contents
        content = resp.raw_response.content
        if isinstance(content, bytes):
            # Avoid large or tiny pages (possible traps or dead pages)
            if len(content) > MAX_PAGE_SIZE:
                print(f"Skipping large page: {url} ({len(content)} bytes)")			# DEBUGGING ########################
                return list()
            if len(content) < MIN_PAGE_SIZE:
                print(f"Skipping tiny page: {url} ({len(content)} bytes) ")			# DEBUGGING ########################
                return list()
            
            try:
                content = content.decode('utf-8', errors='ignore')
            except:
                content = str(content)

        # Tokenize and filter webpages for duplicates
        if not content_filter.should_expand_page(content):
            return list()
    
        soup = BeautifulSoup(content, 'html.parser')
        
        # Get the base URL to resolve relative URLs
        base_url = resp.url if hasattr(resp, 'url') and resp.url else url
        
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            
            # Skip invalid protocols and non-webpage links
            if href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
                continue

            absolute_url = urljoin(base_url, href)
            
            absolute_url = urldefrag(absolute_url)[0]
            print(f"URL: {absolute_url}")					# DEBUGGING ########################


            links.add(absolute_url)
        
        return list(links)
    
    except Exception:
        return list()

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        if not url or not url.strip():
            return False
        
        parsed = urlparse(url)
        
        # Check URL scheme
        if parsed.scheme not in ("http", "https"):
            return False
        
        # Check if domain is in allowed domains
        allowed_domains = [
            r'.*\.ics\.uci\.edu',
            r'.*\.cs\.uci\.edu',
            r'.*\.informatics\.uci\.edu',
            r'.*\.stat\.uci\.edu'
        ]
        
        # Check if the netloc matches any allowed domain
        domain_valid = any(re.match(domain, parsed.netloc) for domain in allowed_domains)
        if not domain_valid:
            return False
        
        # Check path depth
        path_depth = len(parsed.path.split('/'))
        if path_depth > MAX_PATH_DEPTH:
            return False

        # Check for calendar pattern
        calendar_pattern = r'(/\d{4}/){2,}'				# Repeated two repeated /YYYY/... patterns
        calendar_pattern2 = r'(/\d{4}/\d{2}/\d{2}/)'	# /YYYY/MM/DD
        if re.search(calendar_pattern, parsed.path) or re.search(calendar_pattern2):
            return False
        
        # Check query length
        if parsed.query:
            query_params = parsed.query.split('&')
            if len(query_params) > MAX_QUERY_LEN:
                return False
        
        # Check file extensions that should not be crawled
        if re.match(BAD_EXTENSIONS_REGEX, parsed.path.lower()):
            return False
        
        return True
    
    except Exception:
        raise

