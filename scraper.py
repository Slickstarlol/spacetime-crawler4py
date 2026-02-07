import re
from urllib.parse import urlparse, urljoin, urldefrag, parse_qs
from bs4 import BeautifulSoup
import content_filter

MAX_PAGE_SIZE = 10 * 1024 * 1024    # 10 MB
MIN_PAGE_SIZE = 100                 # 100 bytes

MAX_PATH_DEPTH = 6
BAD_PATH_KEYS = {"login", "logout", "signup", "sign_up", "signin", "sign_in" "signout", "register", "search", "history", 
				 "diff", "media", "file", "image", "print", "action", "admin", "auth"}

MAX_QUERY_LEN = 5
BAD_QUERY_KEYS = {"ns", "image", "tab", "tab_files", "tab_details", 
				  "do", "diff", "sort", "filter", "view", "action",
				  "auth", "from", "precision", "token", "filter",
				  "search", "share", "outlook-cal", "ical", "keywords"}

BAD_EXTENSIONS_REGEX = (r".*\.(7z|arff|avi|bib|bin|bmp|bz2|c|cnf|css|csv|"
						r"dat|data|dll|dmg|doc|docx|eps|epub|exe|h|"
						r"gif|gz|ico|iso|jar|jpe?g|jpg|js|lif|m4v|mid|"
						r"mkv|mov|mp2|mp3|mp4|mpeg|msi|mso|names|"
						r"odc|ogg|ogv|pdf|png|ppt|pptx|ps|psd|py|ram|"
						r"rar|rm|rtf|sas|sha1|smil|swf|tar|tex|tgz|"
						r"thmx|tiff?|txt|wav|wma|wmv|xls|xlsx|xml|zip)$")

VALID_DOMAINS = [
			r'ics.uci.edu',
			r'cs.uci.edu',
			r'informatics.uci.edu',
			r'stat.uci.edu'
		]



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
				#print(f"Skipping large page: {url} ({len(content)} bytes)")			# DEBUGGING
				return list()
			if len(content) < MIN_PAGE_SIZE:
				#print(f"Skipping tiny page: {url} ({len(content)} bytes) ")			# DEBUGGING
				return list()
			
			try:
				content = content.decode('utf-8', errors='ignore')
			except:
				content = str(content)

		soup = BeautifulSoup(content, 'html.parser')

		# Tokenize and filter webpages for duplicates
		if not content_filter.should_expand_page(soup, resp.url):
			return list()
				
		# Get the base URL to resolve relative URLs
		base_url = resp.url if hasattr(resp, 'url') and resp.url else url
		
		for link in soup.find_all('a', href=True):
			href = link['href'].strip()
			#print(f"Parsing url {href}")												# DEBUGGING
			
			# Skip invalid protocols and non-webpage links
			if href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
				#print("Skipping")														# DEBUGGING
				continue

			absolute_url = urljoin(base_url, href)
			
			absolute_url = urldefrag(absolute_url)[0]
			#print(f"Abs URL: {absolute_url}")											# DEBUGGING

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
			#print("Empty url")															# DEBUGGING
			return False
		
		# Reject extremely long urls
		if len(url) > 200:
			#print(f"Url too long ({url} {len(url)})")									# DEBUGGING
			return False
		
		parsed = urlparse(url)
		
		# Check URL scheme
		if parsed.scheme not in ("http", "https"):
			#print(f"URL scheme invalid: {url}")											# DEBUGGING
			return False
		
		# Check if the netloc matches valid domain
		hostname = parsed.hostname
		domain_valid = any(hostname.endswith(domain) for domain in VALID_DOMAINS)
		if not domain_valid:
			#print(f"Invalid domain: {hostname}")												# DEBUGGING
			return False
		
		# Check path depth
		path_keys = parsed.path.lower().split('/')
		if len(path_keys) > MAX_PATH_DEPTH:
			#print(f"Path too long: {url}")												# DEBUGGING
			return False
		
		# Check bad path keys for UI pages (login, search, signup, etc...)
		if any(key in path_keys for key in BAD_PATH_KEYS):
			print(f"Bad path key: {url}")
			return False

		# Check for calendar pattern in path
		calendar_pattern = r'(/\d{4}/){2,}'				# Repeated two repeated /YYYY/... patterns
		calendar_pattern2 = r'(/\d{4}/\d{2}/\d{2}/)'	# /YYYY/MM/DD
		if re.search(calendar_pattern, parsed.path) or re.search(calendar_pattern2, parsed.path):
			#print(f"Calendar detected: {url}")											# DEBUGGING
			return False
		
		# Check query parameters and actions
		if parsed.query:
			params = parse_qs(parsed.query.lower())
			if any(key in BAD_QUERY_KEYS for key in params):
				#print(f"Bad query key: {url}")											# DEBUGGING
				return False
		
		# Check file extensions that should not be crawled
		if re.match(BAD_EXTENSIONS_REGEX, parsed.path.lower()):
			#print(f"Bad file extension: {url}")											# DEBUGGING
			return False
		
		return True
	
	except Exception:
		raise

