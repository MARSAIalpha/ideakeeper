import urllib.request
import re
import json

url = "https://www.xiaohongshu.com/explore/685e78b5000000001c030b19?note_flow_source=wechat&xsec_token=CBQe3cRW2015atwFltdOrtUNACjXV7alWQIc5QnCx52Xk="
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        # Look for window.__INITIAL_STATE__
        match = re.search(r'window\.__INITIAL_STATE__=({.*?});</script>', html)
        if match:
            state = json.loads(match.group(1))
            note_id = state.get("note", {}).get("currentNoteId")
            note_detail = state.get("note", {}).get("noteDetailMap", {}).get(note_id, {}).get("note", {})
            title = note_detail.get("title", "")
            video_info = note_detail.get("video", {})
            media = video_info.get("media", {})
            stream = media.get("stream", {})
            h264 = stream.get("h264", [])
            print(f"Title: {title}")
            for s in h264:
                print(f"Video URL: {s.get('masterUrl', s.get('videoUrl', ''))}")
        else:
            print("No __INITIAL_STATE__ found. Response length:", len(html))
except Exception as e:
    print(f"Error: {e}")
