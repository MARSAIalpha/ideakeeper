import os
import sys
import json
import requests
import asyncio
from pathlib import Path
from datetime import date
import hashlib

# Add parent directory to path so we can import services
sys.path.append(str(Path(__file__).resolve().parent.parent))

from services.storage import DATA_DIR, create_video_workspace
from services.entity_store import upsert_post, upsert_clothes

def download_file(url: str, dest_path: Path):
    """Download a file from an URL."""
    if not url.startswith("http"):
        return False
        
    # Skip if file already exists and is not empty
    if dest_path.exists() and dest_path.stat().st_size > 1024:
        # print(f"Already exists: {dest_path}")
        return True
        
    print(f"Downloading {url} to {dest_path}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://item.taobao.com/"
    }
    try:
        response = requests.get(url, stream=True, timeout=10, headers=headers)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"✓ Downloaded: {dest_path.name}")
        return True
    except requests.exceptions.Timeout:
        print(f"Timeout downloading {url}")
        return False
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False

def ingest_product(json_file_path: str, url: str):
    print(f"\n--- Processing {json_file_path} ---")
    
    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    title = data.get("title", "Unknown Product")
    print(f"Title: {title}")
    
    # Create workspace using the URL hash as pseudo video_id
    # Incorporate title to avoid collision for different products with same URL (if redirected)
    unique_key = f"{url}_{data.get('title', '')}"
    video_id = hashlib.md5(unique_key.encode()).hexdigest()[:12]
    workspace = create_video_workspace(video_id)
    
    # Ensure images dir exists
    images_dir = workspace["base"] / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    # Download Video
    video_url = data.get("video_url", "")
    video_rel_path = ""
    if video_url:
        video_dest = workspace["base"] / "video.mp4"
        if download_file(video_url, video_dest):
            video_rel_path = f"/data/{video_dest.relative_to(DATA_DIR)}"
            
    # Download Carousel Images
    carousel_paths = []
    for i, img_url in enumerate(data.get("carousel_images", [])):
        img_dest = images_dir / f"carousel_{i}.jpg"
        if download_file(img_url, img_dest):
            carousel_paths.append(f"/data/{img_dest.relative_to(DATA_DIR)}")
            
    # Download Detail Images
    detail_paths = []
    for i, img_url in enumerate(data.get("detail_images", [])):
        img_dest = images_dir / f"detail_{i}.jpg"
        if download_file(img_url, img_dest):
            detail_paths.append(f"/data/{img_dest.relative_to(DATA_DIR)}")
            
    print(f"Downloaded {len(carousel_paths)} carousel images and {len(detail_paths)} detail images.")
    
    # Primary image (either first carousel or first detail)
    primary_image_rel_path = ""
    if carousel_paths:
        primary_image_rel_path = carousel_paths[0]
    elif detail_paths:
        primary_image_rel_path = detail_paths[0]
        
    # Combine description and selling points
    desc = title + "\n" + "\n".join(data.get("selling_points", []))
    
    clothes_ids = []
    if primary_image_rel_path:
        print(f"Registering clothes entity...")
        from services.vector_store import add_asset_to_vector_store
        
        # Add to vector store
        add_asset_to_vector_store(
            "clothes", 
            Path(primary_image_rel_path).stem, 
            desc, 
            primary_image_rel_path
        )
        
        c_cls = {
            "category": "女装" if "连衣裙" in title or "女" in title else "服饰",
            "color": "咖色/米色" if "咖色" in title else ("白色" if "白" in title else "未知"),
            "display_name": title[:30] + "..." if len(title) > 30 else title
        }
        
        # Register main clothes item
        # Use a more specific clothes_id to avoid sharing assets across products
        product_unique_id = f"clothes_{video_id}"
        cid = upsert_clothes(primary_image_rel_path, c_cls, desc, video_id, clothes_id=product_unique_id)
        
        # Add gallery
        all_images = carousel_paths + detail_paths
        for img_path in all_images:
            if img_path != primary_image_rel_path:
                upsert_clothes(img_path, c_cls, desc, video_id, clothes_id=cid)
                
        clothes_ids.append(cid)

    print(f"Registering post entity...")
    date_str = date.today().isoformat()
    analysis = {
        "topic": title,
        "selling_points": data.get("selling_points", []),
        "summary": "淘宝商品导入提取"
    }
    
    upsert_post(
        post_id=video_id,
        source_url=url,
        date=date_str,
        actor_ids=[],
        clothes_ids=clothes_ids,
        scene_ids=[],
        transcript="",
        analysis=analysis,
        thumbnail_url=primary_image_rel_path,
        video_url=video_rel_path
    )
    
    print(f"✓ Successfully ingested {title}")

if __name__ == "__main__":
    import yaml
    
    # Example usage:
    # brain_dir = Path("C:/Users/simon/.gemini/antigravity/brain/7796040a-e7cb-4a25-b791-e07c11028a97")
    # ingest_product(
    #     str(brain_dir / "taobao_data.json"), 
    #     "https://e.tb.cn/h.i01KAkrHPuLV96K?tk=JXc1UJLgjjv"
    # )
    
    # script_dir = Path(__file__).parent
    # ingest_product(
    #     str(script_dir / "data" / "taobao_data_pannpann.json"), 
    #     "https://e.tb.cn/h.i18bXhzbrXFj6ve?tk=k6JgUsCHtrv"
    # )
    
    print("Ready for ingestion. Please uncomment the desired product call in the __main__ block.")
