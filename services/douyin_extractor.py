import asyncio
import os
import requests
from pathlib import Path
from playwright.async_api import async_playwright
from services.taobao_extractor import HEADERS

def is_douyin_url(url: str) -> bool:
    return "douyin.com" in url or "iesdouyin.com" in url

async def fetch_douyin_media(url: str, dest_dir: Path) -> dict:
    """
    Extracts Douyin video using Playwright.
    """
    print(f"[Douyin] Attempting Playwright extraction for: {url}")
    
    video_url = await _extract_video_url_with_playwright(url)
    
    if video_url:
        video_path = dest_dir / "video.mp4"
        if _download_file(video_url, video_path):
            print(f"[*] Douyin video saved to {video_path}")
            return {"type": "video", "video_path": video_path}
            
    print("[-] Douyin Playwright extraction failed to find video.")
    return {"type": "none"}

async def _extract_video_url_with_playwright(url: str) -> str:
    extracted_urls = set()
    try:
        async with async_playwright() as p:
            # Douyin often requires a mobile user agent for the share page
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
            )
            page = await context.new_page()
            
            try:
                print(f"[Douyin] Navigating to {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(4)

                
                # Check DOM for <video> tags and window._ROUTER_DATA
                dom_video = await page.evaluate("""
                    () => {
                        const v = document.querySelector('video');
                        if (v && v.src) return [v.src];
                        if (window._ROUTER_DATA) {
                            let str = JSON.stringify(window._ROUTER_DATA);
                            let matches = str.match(/https:\\/\\/[^"']+(?:playwm|play\\/\\?video_id|v[0-9]+[^"']+douyinvod)[^"']+/g);
                            return matches;
                        }
                        return null;
                    }
                """)
                if dom_video:
                    for u in dom_video:
                        print(f"[Douyin] Found video from DOM/Router: {u}")
                        extracted_urls.add(u)
                else:
                    print("[Douyin] No video found in DOM.")
                    
            except Exception as e:
                print(f"[Douyin] Playwright error: {e}")
            finally:
                await browser.close()
    except Exception as e:
        print(f"[Douyin] Playwright setup error: {e}")

    # Prioritize non-blob URLs and those with typical Douyin CDN patterns
    candidates = [u for u in extracted_urls if u.startswith("http") and not u.startswith("blob:")]
    for c in candidates:
        if "douyinvod.com" in c or "amemv.com" in c or "playwm" in c or "play/?video_id" in c or ".mp4" in c:
            # remove watermark parameter by replacing playwm with play
            if "playwm" in c:
                c = c.replace("playwm", "play")
            return c
            
    return None

def _download_file(url: str, dest_path: Path) -> bool:
    try:
        # Use a mobile-like header for download too
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.douyin.com/"
        }
        r = requests.get(url, stream=True, timeout=30, headers=headers)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"[-] Download failed: {e}")
        return False
