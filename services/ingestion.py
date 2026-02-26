import os
import requests
import hashlib
from urllib.parse import urlparse
from pathlib import Path
from pydantic import BaseModel, HttpUrl

VIDEO_DOWNLOADER_API_URL = os.getenv("VIDEO_DOWNLOADER_API_URL", "https://zj.v.api.aa1.cn/api/jx-dywm/")

class IngestionRequest(BaseModel):
    url: str
    source: str = "openclaw"

def get_video_id(url: str) -> str:
    """Generate a unique ID for the post based on its URL."""
    return hashlib.md5(url.encode()).hexdigest()[:12]

async def fetch_media(url: str, dest_dir: Path) -> dict:
    """
    Downloads media from the given URL using yt-dlp.
    Supports video posts, image/photo gallery posts, and Taobao product pages.
    
    Returns:
        dict with keys:
            - "type": "video" | "images" | "none"
            - "video_path": Path (if video)
            - "image_paths": list[Path] (if images)
    """
    import subprocess
    import glob
    import tempfile

    # --- Douyin: resolve short links first ---
    # Note: e.tb.cn (Taobao short links) are handled directly by fetch_taobao_media
    # via Playwright, which can follow JS redirects properly.
    if "v.douyin.com" in url:
        try:
            from services.taobao_extractor import HEADERS as TB_HEADERS
            import re
            r = requests.get(url, allow_redirects=True, timeout=5, headers=TB_HEADERS)
            html = r.text
            match = re.search(r"var\s+url\s*=\s*'([^']+)'", html)
            if match:
                resolved_url = match.group(1)
            else:
                resolved_url = r.url # fallback
                
            print(f"[*] Resolved short link: {url} -> {resolved_url}")
            
            # Re-check Douyin Mall or other extractors after resolution
            from services.jinritemai_extractor import is_jinritemai_url, fetch_jinritemai_media
            if is_jinritemai_url(resolved_url):
                return fetch_jinritemai_media(resolved_url, dest_dir)
                
            url = resolved_url  # Use resolved for further checks
        except Exception as e:
            print(f"[-] Resolution failed for {url}: {e}")
            pass

    # --- Taobao / Tmall / Douyin / Xiaohongshu: dedicated extractors ---
    from services.taobao_extractor import is_taobao_url, fetch_taobao_media
    from services.douyin_extractor import is_douyin_url, fetch_douyin_media
    from services.xiaohongshu_extractor import is_xiaohongshu_url, fetch_xiaohongshu_media
    from services.jinritemai_extractor import is_jinritemai_url
    
    if is_taobao_url(url):
        return await fetch_taobao_media(url, dest_dir)
    elif is_douyin_url(url):
        return await fetch_douyin_media(url, dest_dir)
    elif is_jinritemai_url(url):
        from services.jinritemai_extractor import fetch_jinritemai_media
        return fetch_jinritemai_media(url, dest_dir)
    elif is_xiaohongshu_url(url):
        return fetch_xiaohongshu_media(url, dest_dir)

    print(f"[*] Extracting media from: {url}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="xhs_dl_"))
    tmp_pattern = str(tmp_dir / "%(title)s_%(id)s.%(ext)s")

    base_cmd = [
        "yt-dlp",
        "--cookies-from-browser", "chrome",
        "--merge-output-format", "mp4",
        "--user-agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "--add-header", "Referer:https://www.douyin.com/",
        "-o", tmp_pattern,
        url
    ]

    # 1. Try to download as video
    try:
        result = subprocess.run(base_cmd, check=True, capture_output=True)
        # Find mp4
        videos = list(tmp_dir.glob("*.mp4"))
        if videos:
            video_path = dest_dir / "video.mp4"
            videos[0].rename(video_path)
            print(f"[*] Video saved to {video_path}")
            return {"type": "video", "video_path": video_path}
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="ignore")
        print(f"[-] yt-dlp video attempt failed: {stderr[:300]}")

    # 2. It's likely an image gallery — try downloading all formats
    print("[*] Trying image gallery download...")
    img_pattern = str(tmp_dir / "%(title)s_%(id)s_%(autonumber)s.%(ext)s")
    img_cmd = [
        "yt-dlp",
        "--cookies-from-browser", "chrome",
        "--user-agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "--add-header", "Referer:https://www.douyin.com/",
        "-o", img_pattern,
        "--write-all-thumbnails",   # grabs embedded images
        url
    ]
    try:
        subprocess.run(img_cmd, capture_output=True)  # don't check=True since it may still error
    except Exception as e:
        print(f"[-] Image download also failed: {e}")

    # Collect all image files (jpg, png, webp)
    images_dir = dest_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    found_images = []
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
        found_images.extend(tmp_dir.glob(ext))

    if found_images:
        saved_paths = []
        for i, img in enumerate(sorted(found_images)):
            target = images_dir / f"image_{i+1:03d}{img.suffix}"
            img.rename(target)
            saved_paths.append(target)
        print(f"[*] Saved {len(saved_paths)} images to {images_dir}")
        return {"type": "images", "image_paths": saved_paths}

    print("[-] No media could be downloaded.")
    return {"type": "none"}


# --- Legacy byte-based function kept for backward compatibility ---
def fetch_no_watermark_video(url: str) -> bytes:
    """
    Legacy function: Downloads a video and returns raw bytes.
    Not used for image posts.
    """
    import subprocess
    import glob
    import tempfile

    tmp_path = os.path.join(tempfile.gettempdir(), f"download_{hashlib.md5(url.encode()).hexdigest()[:8]}")

    cmd = [
        "yt-dlp",
        "-o", f"{tmp_path}.%(ext)s",
        "--merge-output-format", "mp4",
        "--cookies-from-browser", "chrome",
        url
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        downloaded_files = glob.glob(f"{tmp_path}.*")
        if not downloaded_files:
            print("[-] No files were downloaded by yt-dlp subprocess!")
            return b""
        with open(downloaded_files[0], "rb") as f:
            return f.read()
    except subprocess.CalledProcessError as e:
        print(f"[-] yt-dlp failed: {e.stderr.decode('utf-8')}")
        return b""
    finally:
        for f in glob.glob(f"{tmp_path}.*"):
            try:
                os.remove(f)
            except:
                pass
