import os
import re
import json
import urllib.request
import urllib.parse
from pathlib import Path

def is_xiaohongshu_url(url: str) -> bool:
    return "xiaohongshu.com" in url or "xhslink.com" in url

def fetch_xiaohongshu_media(url: str, output_dir: Path) -> dict:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            # Find title
            title_match = re.search(r'<title>(.*?)</title>', html)
            title = title_match.group(1).replace(' - 小红书', '').strip() if title_match else "xhs_video"
            
            # Find video URL
            video_url = None
            master_url_match = re.search(r'"masterUrl":"(.*?)"', html)
            if master_url_match:
                video_url = master_url_match.group(1).encode('utf-8').decode('unicode_escape').replace('\\/', '/')
            else:
                video_url_match = re.search(r'"videoUrl":"(.*?)"', html)
                if video_url_match:
                    video_url = video_url_match.group(1).encode('utf-8').decode('unicode_escape').replace('\\/', '/')
            
            if not video_url or not video_url.startswith("http"):
                raise ValueError("No video URL found in page source (might be images only)")
                
            output_dir.mkdir(parents=True, exist_ok=True)
            video_path = output_dir / "video.mp4"
            
            print(f"[*] Downloading XHS video: {title}")
            
            vid_req = urllib.request.Request(video_url, headers=headers)
            with urllib.request.urlopen(vid_req) as vid_resp, open(video_path, "wb") as f:
                f.write(vid_resp.read())
                
            return {
                "type": "video",
                "video_path": video_path,
                "title": title
            }
                
    except Exception as e:
        print(f"[-] XHS extraction failed: {e}")
        raise
