import json

def read_json_file(file_path: str) -> dict:
    """
    Reads report file and returns its contents as a dictionary.
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data


def get_count_unique_urls(data: dict) -> int:
    """
    Extracts unique URLs from data dictionary.
    """
    return len(set(data.get("unique_urls", [])))

def get_longest_page_info(data: dict) -> tuple:
    """
    Extracts  longest page information (URL, word count) from data dictionary.
    """
    longest_page = data.get("longest_page", {})
    return longest_page.get("url", ""), longest_page.get("word_count", 0)

def get_50_most_common_words(data: dict) -> list:
    """
    Extracts 50 most common words from data dictionary.
    """
    word_freq = data.get("word_freq", {})
    return sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:50]

def get_subdomain_report(data: dict) -> list:   
    """
    Extracts the subdomain report from data dictionary.
    Returns sorted list of (subdomain, count) tuples.
    """
    subdomain_pages = data.get("subdomain_pages", {})
    return sorted(((sub, len(urls)) for sub, urls in subdomain_pages.items()), key=lambda x: x[0])

def write_report(data: dict, path: str = "report.txt") -> None:
    """
    Writes report containing crawl statistics to a text file.

    Unique Pages:
    (count)

    Longest page:
    (url)
    (word count)

    50 Most Common Words:
    (word: count)

    Unique subdomains:
    (subdomain, # of unique pages)
    ...
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            # 1. Number of unique pages
            unique_count = get_count_unique_urls(data)
            f.write(f"Unique Pages Found: {unique_count}\n\n")
            
            # 2. Longest page information
            longest_url, longest_word_count = get_longest_page_info(data)
            f.write(f"Longest Page (by word count):\n")
            f.write(f"URL: {longest_url}\n")
            f.write(f"Word Count: {longest_word_count}\n\n")
            
            # 3. 50 most common words
            f.write(f"50 Most Common Words:\n")
            common_words = get_50_most_common_words(data)
            for word, freq in common_words:
                f.write(f"{word}: {freq}\n")
            f.write("\n")
            
            # 4. Subdomains in uci.edu with page counts
            f.write(f"Subdomains in uci.edu (alphabetically ordered):\n")
            subdomains = get_subdomain_report(data)
            for subdomain, count in subdomains:
                f.write(f"{subdomain}, {count}\n")
                
    except IOError as e:
        print(f"Error writing report to {path}: {e}")
        
if __name__ == "__main__":
    # Example usage
    data = read_json_file("report.json")
    write_report(data, "report.txt")