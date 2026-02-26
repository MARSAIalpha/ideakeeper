import re
import json
import requests
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
}

def is_jinritemai_url(url: str) -> bool:
    """Check if the URL is a Douyin Mall / Jinritemai link."""
    return any(domain in url for domain in ["jinritemai.com", "douyin.com/ecommerce"])

def fetch_jinritemai_media(url: str, dest_dir: Path) -> dict:
    """
    Resolves the Douyin redirect and extracts product images from query parameters.
    Returns dict with image_paths if successful.
    """
    print(f"[Jinritemai] Processing link: {url}")
    
    try:
        # 1. Resolve redirect to get the full mall URL
        # We use a session and follow redirects
        session = requests.Session()
        resp = session.get(url, headers=HEADERS, allow_redirects=True, timeout=10)
        final_url = resp.url
        print(f"[Jinritemai] Resolved to: {final_url}")
        
        # 2. Parse query parameters from the final URL
        parsed = urlparse(final_url)
        params = parse_qs(parsed.query)
        
        image_urls = []
        
        # Check 'product_info' or 'img' or even unquote the whole query string
        # Looking at the yt-dlp output, the info is often in a double-encoded parameter
        
        # Strategy: Search all parameter values for image patterns
        for key, values in params.items():
            for val in values:
                # Deep unquote
                decoded = unquote(unquote(val))
                # Look for image URLs
                found = re.findall(r'https?://[a-zA-Z0-9\.\-]+\.(?:com|cn)/img/[^" \x27>]*', decoded)
                image_urls.extend(found)
        
        if not image_urls:
            # Fallback: Scrape the HTML for any image tags or JSON blobs if redirect didn't have it
            print("[Jinritemai] No images in query params, trying HTML scrape...")
            image_urls = _extract_images_from_html(resp.text)

        if not image_urls:
            print("[Jinritemai] Failed to find any product images.")
            return {"type": "none"}

        # 3. Download the images
        return _download_images(image_urls, dest_dir, session)

    except Exception as e:
        print(f"[Jinritemai] Error: {e}")
        return {"type": "none"}

def _extract_images_from_html(html: str) -> list[str]:
    """Fallback to search HTML for image patterns."""
    found = set()
    # Typical jinritemai image CDN pattern
    for match in re.finditer(r'https?://[a-zA-Z0-9\.\-]+\.(?:ecombdimg|byteimg)\.com/[^" \x27>]*', html):
        found.add(match.group(0))
    return list(found)

def _download_images(image_urls: list[str], dest_dir: Path, session: requests.Session) -> dict:
    """Downloads unique images to the workspace."""
    images_dir = dest_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    seen_urls = set()
    
    # Take up to 10 unique images
    for i, url in enumerate(image_urls):
        if url in seen_urls: continue
        seen_urls.add(url)
        
        try:
            # Clean url (sometimes they have trailing junk from regex)
            clean_url = url.split('~')[0] if '~' in url else url
            if not clean_url.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                clean_url += '.jpg' # default to jpg if no ext

            r = session.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                suffix = '.jpg'
                if 'image/png' in r.headers.get('Content-Type', ''): suffix = '.png'
                elif 'image/webp' in r.headers.get('Content-Type', ''): suffix = '.webp'
                
                target = images_dir / f"image_{len(saved_paths)+1:03d}{suffix}"
                target.write_bytes(r.content)
                saved_paths.append(target)
                
            if len(saved_paths) >= 8: break
        except Exception as e:
            print(f"[Jinritemai] Failed to download {url}: {e}")

    if saved_paths:
        print(f"[Jinritemai] Successfully saved {len(saved_paths)} images.")
        return {"type": "images", "image_paths": saved_paths}
    
    return {"type": "none"}
