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
    """
    print(f"[Taobao] Fetching product page: {url}")
    session = requests.Session()

    # --- Strategy 1: Playwright with Desktop UA ---
    video_urls, thumbnail_path, image_urls, attributes = await _extract_video_url_with_playwright(url, dest_dir)

    # --- Strategy 1B: Fallback HTML Regex for images ---
    if not image_urls:
        print("[Taobao] Playwright found no images, trying raw HTML extraction...")
        try:
            r = session.get(url, headers=HEADERS, timeout=15)
            r.encoding = 'utf-8'
            html = r.text
            import re
            raw_imgs = re.findall(r'(?:https?:)?//(?:img\.alicdn\.com|gw\.alicdn\.com)[^\s",\\]+(?:\.jpg|\.png)', html)
            for img in raw_imgs:
                high_res = re.sub(r'_\d+x\d+.*\.jpg$', '', img)
                high_res = re.sub(r'_\.webp$', '', high_res)
                if 'TB1' not in high_res and 'icon' not in high_res.lower() and 'blank' not in high_res.lower():
                    image_urls.append(high_res)
            image_urls = list(set(image_urls))
        except Exception as e:
            print(f"[Taobao] Raw HTML fallback error: {e}")

    # --- Strategy 2: Direct mobile API ---
    if not video_urls and not image_urls:
        video_urls = _try_taobao_mobile_api(url, session)

    if not video_urls and not image_urls:
        print("[Taobao] Could not locate any media in this product page.")
        return {"type": "none"}

    print(f"[Taobao] Found {len(video_urls)} candidate video(s) and {len(image_urls)} candidate image(s) after selective filtering.")
    if video_urls:
        print(f"[Taobao] First video URL: {video_urls[0][:100]}...")
    
    result = {"type": "none"}
    if video_urls:
        result = _download_video(video_urls[0], dest_dir, session)
        
    images_dir = dest_dir / "images"
    downloaded_images = []
    if image_urls:
        images_dir.mkdir(parents=True, exist_ok=True)
        for i, img_url in enumerate(list(set(image_urls))[:50]):
            ext = img_url.split('.')[-1].split('?')[0]
            if ext not in ['jpg', 'jpeg', 'png', 'webp']:
                ext = 'jpg'
            img_path = images_dir / f"image_{i+1:03d}.{ext}"
            
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif not img_url.startswith('http'):
                continue
                
            try:
                r = session.get(img_url, headers=HEADERS, stream=True, timeout=10)
                if r.status_code == 200:
                    with open(img_path, 'wb') as f:
                        for chunk in r.iter_content(1024 * 64):
                            f.write(chunk)
                    if img_path.stat().st_size > 5000:
                        downloaded_images.append(img_path)
                    else:
                        img_path.unlink()
            except Exception as e:
                pass
                
        print(f"[Taobao] Downloaded {len(downloaded_images)} images.")
    
    if video_urls and downloaded_images:
        result["type"] = "video_and_images"
        result["image_paths"] = downloaded_images
    elif downloaded_images:
        result["type"] = "images"
        result["image_paths"] = downloaded_images

    if thumbnail_path and thumbnail_path.exists():
        result["thumbnail_path"] = thumbnail_path
        
    # Add extracted attributes to the result
    if attributes:
        result["attributes"] = attributes
        print(f"[Taobao] Extracted {len(attributes)} product attributes.")
        
    return result


async def _extract_video_url_with_playwright(url: str, dest_dir: Path) -> tuple[list[str], Path | None, list[str], dict]:
    """Use Playwright to render the page and capture media + attributes."""
    print("[Taobao] Attempting Playwright extraction...")
    extracted_urls = set()
    extracted_images = set()
    extracted_attributes = {}
    thumbnail_path = None
    try:
        profile_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "taobao_profile")))
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        async with async_playwright() as p:
            desktop_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                slow_mo=500,
                user_agent=desktop_ua,
                viewport={"width": 1280, "height": 800}
            )
            
            tb_cookie = os.getenv("TAOBAO_COOKIE")
            if tb_cookie:
                cookies = []
                for part in tb_cookie.split(";"):
                    if "=" in part:
                        k, v = part.strip().split("=", 1)
                        cookies.append({"name": k, "value": v, "domain": ".taobao.com", "path": "/"})
                        cookies.append({"name": k, "value": v, "domain": ".tmall.com", "path": "/"})
                await context.add_cookies(cookies)
            
            page = await context.new_page()
            
            def on_response(response):
                low_url = response.url.lower()
                if ".mp4" in low_url or ".m3u8" in low_url or response.request.resource_type == "media":
                    extracted_urls.add(response.url)
                if "alicdn.com" in low_url or "tbcdn.cn" in low_url or response.request.resource_type == "image":
                    if any(ext in low_url for ext in [".jpg", ".png", ".webp", ".jpeg"]):
                        extracted_images.add(response.url)
            
            page.on("response", on_response)
            
            try:
                print(f"[Taobao] Navigating to {url}")
                await page.goto(url, wait_until="commit", timeout=60000)
                
                try:
                    await page.wait_for_selector(".detail-content, .desc-img, #desc, #J_DivItemDesc, .Attributes-list", timeout=10000)
                except:
                    pass
                
                # Scroll to reveal all content
                for _ in range(10):
                    await asyncio.sleep(0.5)
                    await page.evaluate("window.scrollBy(0, window.innerHeight);")
                
                # Debug: dump text to see what we have
                page_text = await page.evaluate("document.body.innerText.substring(0, 2000)")
                print(f"[Taobao] Page Text Extract: {page_text.replace('\\n', ' ')}")
                
                # Capture attributes first
                extracted_attributes = await page.evaluate(r"""
                    () => {
                        const attrs = {};
                        console.log("Starting attribute extraction JS...");
                        
                        // Helper to add attribute
                        const addAttr = (k, v) => {
                            if (k && v && typeof k === 'string' && typeof v === 'string') {
                                const cleanK = k.trim().replace(/[:：\s]/g, '');
                                const cleanV = v.trim();
                                if (cleanK && cleanV) {
                                    attrs[cleanK] = cleanV;
                                    console.log(`Extracted: ${cleanK} = ${cleanV}`);
                                }
                            }
                        };

                        // 1. Common table-like attributes
                        const listItems = document.querySelectorAll('#J_AttrUL li, .params-list li, .Attributes-list li, .attrs-list li, .p-list li, .tm-attr-list li, [class*="emphasisParamsInfoItem"]');
                        console.log(`Found ${listItems.length} candidate list items`);
                        
                        listItems.forEach(li => {
                            // Check for internal label/value pairs first (new Tmall layout)
                            const labelEl = li.querySelector('[class*="SubTitle"], .label, .name, .attr-name');
                            const valueEl = li.querySelector('[class*="Title"], .value, .val, .attr-value');
                            
                            if (labelEl && valueEl) {
                                addAttr(labelEl.innerText, valueEl.innerText);
                            } else {
                                // Fallback to colon-separated text
                                let text = li.innerText.trim();
                                if (text.includes(':') || text.includes('：')) {
                                    const parts = text.split(/[:：]/);
                                    if (parts.length >= 2) {
                                        addAttr(parts[0], parts.slice(1).join(':'));
                                    }
                                }
                            }
                        });

                        // 2. Grid-like parameters
                        const gridItems = document.querySelectorAll('.param-item, .attribute-item, .spec-item, .tm-attribute-item');
                        gridItems.forEach(item => {
                            const k = item.querySelector('.label, .name, .attr-name')?.innerText.trim();
                            const v = item.querySelector('.value, .val, .attr-value')?.innerText.trim();
                            addAttr(k, v);
                        });

                        // 3. Simple text pairs in div/span
                        document.querySelectorAll('.prop-item, .p-prop').forEach(item => {
                             const spans = item.querySelectorAll('span');
                             if (spans.length >= 2) {
                                 addAttr(spans[0].innerText, spans[1].innerText);
                             }
                        });

                        // 4. Try extract from window variables
                        try {
                            const scripts = Array.from(document.querySelectorAll('script')).map(s => s.innerText);
                            for (const script of scripts) {
                                if (script.includes('apiStack') || script.includes('__INITIAL_DATA__')) {
                                    const brandMatch = script.match(/"品牌":"([^"]+)"/) || script.match(/"brandName":"([^"]+)"/);
                                    if (brandMatch) addAttr("品牌", brandMatch[1]);
                                    
                                    const snMatch = script.match(/"货号":"([^"]+)"/) || script.match(/"model":"([^"]+)"/);
                                    if (snMatch) addAttr("货号", snMatch[1]);
                                }
                            }
                        } catch (e) {}

                        return attrs;
                    }
                """)
                print(f"[Taobao] Extracted {len(extracted_attributes)} attributes")
                
                # Capture screenshot
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    thumbnail_path = dest_dir / "thumbnail.jpg"
                    await page.screenshot(path=str(thumbnail_path), full_page=False)
                except:
                    thumbnail_path = None
                
                # Extract images
                image_srcs = await page.evaluate(r"""
                    () => {
                        const imgs = [];
                        const addUrl = (url) => {
                            if (!url || typeof url !== 'string') return;
                            let clean = url.trim();
                            if (clean.startsWith('//')) clean = 'https:' + clean;
                            if (!clean.startsWith('http')) return;
                            if (clean.includes('.gif') || clean.includes('icon') || clean.includes('blank') || clean.includes('spacer')) return;
                            // Clean Taobao thumbnail suffixes
                            clean = clean.replace(/_\d+x\d+.*\.jpg$/, '').replace(/_.webp$/, '').replace(/_\d+x\d+.*\.png$/, '');
                            if (!imgs.includes(clean)) imgs.push(clean);
                        };

                        // 1. Look for main product image containers (High priority)
                        const selectors = [
                            '#J_UlThumb',                // Taobao Desktop Thumbs
                            '.tm-detail-gallery',        // Tmall Desktop Gallery
                            '.main-img',                 // Common Tmall
                            '#J_ImgCanvas',              // Taobao Main
                            '.module-adds',              // Detail images (often huge)
                            '.desc_anchor',              // Description area
                            '#description',              // Description area
                            '.ke-post'                   // Rich text content
                        ];
                        
                        selectors.forEach(sel => {
                            const container = document.querySelector(sel);
                            if (container) {
                                container.querySelectorAll('img').forEach(img => {
                                    let src = img.getAttribute('data-src') || img.src || img.getAttribute('data-ks-lazyload') || img.getAttribute('data-actualsrc') || img.getAttribute('original');
                                    if (src && !src.includes('TB1') && !src.includes('icon')) {
                                        addUrl(src);
                                    }
                                });
                            }
                        });

                        // 2. Fallback: if nothing found, grab large images only
                        if (imgs.length === 0) {
                            document.querySelectorAll('img').forEach(img => {
                                if (img.width > 300 || img.height > 300) {
                                    let src = img.getAttribute('data-src') || img.src;
                                    addUrl(src);
                                }
                            });
                        }
                        return imgs;
                    }
                """)
                for i in image_srcs:
                    if i: extracted_images.add(i)
                
            except Exception as e:
                print(f"[Taobao] Playwright navigation error: {e}")
            finally:
                await context.close()
    except Exception as e:
        print(f"[Taobao] Playwright setup error: {e}")

    valid_urls = [u for u in extracted_urls
            if (".mp4" in u or "video" in u.lower())
            and ("alicdn.com" in u or "cloud.video.taobao.com" in u)]
            
    final_images = sorted(list(set(extracted_images)))
    return valid_urls, thumbnail_path, final_images, extracted_attributes


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
