import os
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Dictionary to map platforms to their risk scores
PLATFORM_RISK = {
    "streameast.io": 1.0,
    "rojadirecta": 1.0,
    "telegram.me": 0.8,
    "t.me": 0.8,
    "reddit.com": 0.5,
    "dailymotion.com": 0.6,
    "youtube.com": 0.3,
    "streamable.com": 0.7,
    "vimeo.com": 0.4,
    "default": 0.6
}

def classify_platform_risk(url):
    """
    Extracts the domain from a given URL and returns the corresponding risk score.
    Returns 0.6 (default) for unknown domains.
    """
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
            
        for key, score in PLATFORM_RISK.items():
            if key != "default" and key in domain:
                return score
                
        return PLATFORM_RISK["default"]
    except Exception:
        return PLATFORM_RISK["default"]

def get_page_thumbnail(url):
    """
    Fetches the page and extracts the og:image or the first img src.
    Returns the image URL or None if it fails.
    """
    try:
        # Set a 5-second timeout to avoid blocking
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for Open Graph image meta tag
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return og_image['content']
            
        # Fallback to the first image tag
        first_img = soup.find('img')
        if first_img and first_img.get('src'):
            src = first_img['src']
            if src.startswith('http'):
                return src
            else:
                from urllib.parse import urljoin
                return urljoin(url, src)
                
        return None
    except requests.RequestException:
        return None

def detect_anomaly(detections_count, hours_elapsed):
    """
    Calculates the spread velocity (detections per hour).
    Returns True and an alert message if velocity > 10, otherwise False and a normal message.
    """
    if hours_elapsed <= 0:
        return False, "Normal: Elapsed time must be greater than 0."
        
    velocity = detections_count / hours_elapsed
    
    if velocity > 10:
        return True, f"ALERT: High spread velocity detected! {velocity:.2f} detections per hour."
    else:
        return False, f"Normal: Spread velocity is {velocity:.2f} detections per hour."

def hunt_for_content(asset_title, content_type, keywords, search_api_key=None, cx_id=None):
    """
    Builds search queries based on content type, calls Google Custom Search API,
    deduplicates results, and evaluates the risk for each discovered URL.
    """
    # Load keys from .env if they are not provided
    if search_api_key is None:
        search_api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    if cx_id is None:
        cx_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        
    if not search_api_key or not cx_id:
        print("Warning: Google Custom Search API key or Engine ID is missing.")
        return []

    # Build base query and decide modifiers based on content_type
    queries = []
    base_query = f'"{asset_title}" {" ".join(keywords)}'
    
    modifiers = []
    if content_type == "sports":
        modifiers = ["highlights", "free stream", "full match"]
    elif content_type == "film":
        modifiers = ["full movie", "free watch", "123movies"]
    elif content_type == "music_video":
        modifiers = ["official video", "free download", "mp3"]
    elif content_type == "news":
        modifiers = ["footage", "exclusive", "broadcast"]
    elif content_type == "general":
        modifiers = ["free watch", "unauthorized", "download"]
    else:
        modifiers = ["free watch", "unauthorized", "download"]
        
    # Generate exactly 5 queries
    queries.append(base_query)
    for mod in modifiers:
        queries.append(f"{base_query} {mod}")
        
    # If fewer than 5 queries generated, add a combined modifier query
    if len(queries) < 5:
        queries.append(f"{base_query} {' '.join(modifiers)}")
    
    results = []
    seen_urls = set()
    
    search_url = "https://www.googleapis.com/customsearch/v1"
    
    # Process each query
    for query in queries[:5]:
        params = {
            "key": search_api_key,
            "cx": cx_id,
            "q": query
        }
        
        try:
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            items = data.get("items", [])
            for item in items:
                url = item.get("link")
                
                # Deduplicate by URL
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    domain = urlparse(url).netloc
                    risk_score = classify_platform_risk(url)
                    
                    # Print a status message for each URL found
                    print(f"Hunted URL: {url} | Platform: {domain} | Risk: {risk_score}")
                    
                    results.append({
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                        "query_used": query,
                        "platform": domain,
                        "platform_risk_score": risk_score
                    })
        except requests.RequestException as e:
            print(f"Error fetching results for query '{query}': {e}")
            
    return results
