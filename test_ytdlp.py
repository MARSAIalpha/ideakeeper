from services.ingestion import fetch_no_watermark_video

url = "https://www.xiaohongshu.com/discovery/item/6437e6c60000000013033c1e?source=webshare&xhsshare=pc_web&xsec_token=ABD56ETtHF6l3VF0cE1nUJbk1wcsykUw7AdUqFgFqErMM=&xsec_source=pc_share"
video_bytes = fetch_no_watermark_video(url)
print(f"Downloaded {len(video_bytes)} bytes")
