"""
Taobao/Tmall product video extractor.

Taobao product videos are served from Alibaba's CDN as direct .mp4 files.
We parse the product page HTML to find embedded video URLs, then download them directly
without needing any paid API.

Supported URL formats:
  - https://item.taobao.com/item.htm?id=...
  - https://detail.tmall.com/item.htm?id=...
  - https://m.taobao.com/#/detail?id=...   (mobile)
"""

import os
import re
import json
import requests
import time
from pathlib import Path
import asyncio
from playwright.async_api import async_playwright

# Headers to mimic a real browser visit (mobile UA tends to get simpler JSON pages)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.taobao.com/",
}

# Desktop UA — Taobao serves full HTML with embedded .mp4 URLs to desktop browsers
_DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def is_taobao_url(url: str) -> bool:
    """Return True if the URL is a Taobao or Tmall product page (or short link)."""
    return any(domain in url for domain in [
        "item.taobao.com",
        "detail.tmall.com",
        "m.taobao.com",
        "taobao.com/item",
        "e.tb.cn",
    ])


def _extract_video_urls_from_html(html: str) -> list[str]:
    """
    Search the raw HTML / embedded JavaScript for Alibaba CDN video URLs.
    Taobao pages embed product data in multiple places:
      - window.__INIT_DATA__ = {...}
      - window.g_config = {...}
      - <video src="...">
      - JSON-LD script blocks
    """
    found = set()

    # 1. Direct <video src="..."> tags
    for match in re.finditer(r'<video[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE):
        url = match.group(1)
        if url.endswith(".mp4") or "video" in url:
            found.add(url)

    # 2. JSON-embedded video URLs (common pattern: "videoUrl":"https://...")
    for match in re.finditer(r'"videoUrl"\s*:\s*"([^"]+)"', html):
        found.add(match.group(1).replace("\\u002F", "/"))

    # 3. Alibaba CDN pattern: https://...alicdn.com/...mp4
    for match in re.finditer(r'https?://[a-z0-9\-\.]+alicdn\.com/[^"\'<\s]+\.mp4', html):
        found.add(match.group(0))

    # 4. Taobao video CDN pattern: https://cloud.video.taobao.com/play/u/.../xxx.mp4
    for match in re.finditer(r'https?://cloud\.video\.taobao\.com/[^"\'<\s]+\.mp4[^"\'<\s]*', html):
        found.add(match.group(0))

    # 5. Try parsing window.__INIT_DATA__ as JSON
    init_data_match = re.search(r'window\.__INIT_DATA__\s*=\s*(\{.+?\});\s*</script>', html, re.DOTALL)
    if init_data_match:
        try:
            data = json.loads(init_data_match.group(1))
            # Recursively find any key containing "video" with a URL value
            for url in _find_video_urls_in_dict(data):
                found.add(url)
        except json.JSONDecodeError:
            pass

    # Clean up — remove any URLs that are tracking pixels or thumbnails
    return [u for u in found if ".mp4" in u or "video" in u.lower()]


def _find_video_urls_in_dict(obj, depth=0) -> list[str]:
    """Recursively walk a nested dict/list looking for video URLs."""
    if depth > 10:
        return []
    results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and ("video" in k.lower() or "mp4" in v):
                if v.startswith("http") and (".mp4" in v or "video" in v):
                    results.append(v)
            else:
                results.extend(_find_video_urls_in_dict(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_find_video_urls_in_dict(item, depth + 1))
    return results


async def fetch_taobao_media(url: str, dest_dir: Path) -> dict:
    """
    Fetches a Taobao/Tmall product page, extracts embedded video URLs,
    and downloads the video directly to dest_dir/video.mp4.
    
    Strategy:
      1. Playwright + Desktop UA + cookie injection → renders the full page JS
         and parses the resulting HTML for .mp4 URLs. This is the only reliable
         method since Taobao serves JS-only stubs to plain HTTP requests.
      2. Mobile API fallback for simple cases.
    
    Returns dict with same shape as ingestion.fetch_media():
        {"type": "video", "video_path": Path}  — on success
        {"type": "none"}                         — on failure
    """
    print(f"[Taobao] Fetching product page: {url}")
    session = requests.Session()

    # --- Strategy 1: Playwright with Desktop UA (primary, most reliable) ---
    video_urls = await _extract_video_url_with_playwright(url)

    # --- Strategy 2: Direct mobile API (fallback for item IDs) ---
    if not video_urls:
        video_urls = _try_taobao_mobile_api(url, session)

    if not video_urls:
        print("[Taobao] Could not locate any video in this product page.")
        return {"type": "none"}

    print(f"[Taobao] Found {len(video_urls)} candidate video(s).")
    return _download_video(video_urls[0], dest_dir, session)




async def _extract_video_url_with_playwright(url: str) -> list[str]:
    """Use Playwright with Desktop UA + optional cookie injection to render the page."""
    print("[Taobao] Attempting Playwright extraction...")
    extracted_urls = set()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=_DESKTOP_UA)

            # Inject TAOBAO_COOKIE if available for login bypass
            tb_cookie = os.getenv("TAOBAO_COOKIE")
            if tb_cookie:
                cookies = []
                for part in tb_cookie.split(";"):
                    if "=" in part:
                        k, v = part.strip().split("=", 1)
                        cookies.append({"name": k, "value": v, "domain": ".taobao.com", "path": "/"})
                        cookies.append({"name": k, "value": v, "domain": ".tmall.com", "path": "/"})
                await context.add_cookies(cookies)
                print("[Taobao] Injected login cookies from TAOBAO_COOKIE")
            else:
                print("[Taobao] No TAOBAO_COOKIE set — proceeding without auth")
            page = await context.new_page()
            
            # Watch for video-like network requests
            def on_response(response):
                low_url = response.url.lower()
                if ".mp4" in low_url or ".m3u8" in low_url or response.request.resource_type == "media":
                    extracted_urls.add(response.url)
            
            page.on("response", on_response)
            
            try:
                print(f"[Taobao] Navigating to {url}")
                await page.goto(url, wait_until="load", timeout=45000)
                # Wait for potential lazy loading / player initialization
                for _ in range(3):
                    await asyncio.sleep(2)
                    # Force scroll to trigger lazy loads
                    await page.mouse.wheel(0, 500)
                
                # Also parse the full HTML for embedded video URLs
                html = await page.content()
                html_urls = _extract_video_urls_from_html(html)
                for u in html_urls:
                    extracted_urls.add(u)
                
                # Check video tags more thoroughly
                video_srcs = await page.evaluate("""
                    () => {
                        const srcs = [];
                        document.querySelectorAll('video').forEach(v => {
                            if (v.src) srcs.push(v.src);
                            v.querySelectorAll('source').forEach(s => {
                                if (s.src) srcs.push(s.src);
                            });
                        });
                        return srcs;
                    }
                """)
                for v in video_srcs:
                    if v: extracted_urls.add(v)
                
            except Exception as e:
                print(f"[Taobao] Playwright navigation error: {e}")
            finally:
                await browser.close()
    except Exception as e:
        print(f"[Taobao] Playwright setup error: {e}")

    print(f"[Taobao] Playwright raw URLs found: {len(extracted_urls)}")
    for u in extracted_urls:
        if "alicdn.com" in u:
            print(f"  - Found candidate: {u[:100]}...")

    # Filter for actually valid CDN links (alicdn.com or cloud.video.taobao.com)
    return [u for u in extracted_urls
            if (".mp4" in u or "video" in u.lower())
            and ("alicdn.com" in u or "cloud.video.taobao.com" in u)]


def _try_taobao_mobile_api(url: str, session: requests.Session) -> list[str]:
    """Fallback to direct product ID lookup via mobile-like endpoint."""
    item_id_match = re.search(r'id=(\d+)', url)
    if not item_id_match:
        return []
    item_id = item_id_match.group(1)
    api_url = f"https://item.taobao.com/item.htm?id={item_id}&format=json"
    try:
        r = session.get(api_url, headers=HEADERS, timeout=10)
        return _find_video_urls_in_dict(r.json())
    except Exception:
        return []


def _try_taobao_api(url: str, session: requests.Session) -> list[str]:
    """
    Some Taobao items expose a detail API at /item/detail.json?id=...
    Try this as a fallback.
    """
    item_id_match = re.search(r'id=(\d+)', url)
    if not item_id_match:
        return []
    item_id = item_id_match.group(1)
    api_url = f"https://item.taobao.com/item.htm?id={item_id}&format=json"
    try:
        r = session.get(api_url, headers=HEADERS, timeout=10)
        return _find_video_urls_in_dict(r.json())
    except Exception:
        return []


def _download_video(video_url: str, dest_dir: Path, session: requests.Session) -> dict:
    """Stream-download a video to dest_dir/video.mp4."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    video_path = dest_dir / "video.mp4"
    # Taobao CDN requires item.taobao.com as Referer, otherwise returns '非法访问'
    dl_headers = {
        **HEADERS,
        "Referer": "https://item.taobao.com/",
    }
    try:
        with session.get(video_url, headers=dl_headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(video_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    f.write(chunk)
        size = video_path.stat().st_size
        if size < 10_000:  # Less than 10KB — something went wrong
            print(f"[Taobao] Downloaded file too small ({size} bytes), likely not a real video.")
            video_path.unlink(missing_ok=True)
            return {"type": "none"}
        print(f"[Taobao] Video saved to {video_path} ({size // 1024} KB)")
        return {"type": "video", "video_path": video_path}
    except Exception as e:
        print(f"[Taobao] Download failed: {e}")
        return {"type": "none"}
