import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import shutil
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from services.ingestion import IngestionRequest, get_video_id, fetch_no_watermark_video, fetch_media
from services.storage import create_video_workspace, save_file, DATA_DIR
from services.processor import extract_keyframes
from services.analyzer import analyze_frame
from services.audio_extractor import extract_audio
from services.transcriber import transcribe_audio
from services.script_analyzer import analyze_transcript

load_dotenv()

app = FastAPI(title="Video Asset Library Pipeline")

# Mount frontend and data directories
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
app.mount("/data", StaticFiles(directory="data"), name="data")

from services.segmenter import extract_clothes_render
from services.classifier import classify_actor, classify_clothes
from services.entity_store import upsert_actor, upsert_clothes, upsert_scene, upsert_post

def _run_vla_on_frames(frames: list, workspace: dict, video_id: str) -> dict:
    """
    Run Qwen-VL on frames with color-based deduplication:
    - Clothes: group by (detected_category, detected_color).
    - Aggregate multi-angle descriptions and images into a single product entry.
    """
    from services.vector_store import add_asset_to_vector_store
    
    actor_ids, clothes_ids, scene_ids = [], [], []
    thumbnail_url = ""
    found_actor = False
    scene_count = 0
    MAX_SCENES = 2

    print(f"[{video_id}] Analyzing {len(frames)} frames with VLA...")
    if frames:
        thumbnail_url = f"/data/{frames[0].relative_to(DATA_DIR)}"

    # ══════════════════════════════════════════════════════════════════════
    # PASS 1: Analyze all frames, collect clothes candidates + handle actors/scenes
    # ══════════════════════════════════════════════════════════════════════
    clothes_candidates = []  

    for i, frame_path in enumerate(frames):
        analysis = analyze_frame(frame_path)

        if analysis.get("has_clear_clothes"):
            # Handle new list format first
            if "clothes_items" in analysis and isinstance(analysis["clothes_items"], list):
                for item in analysis["clothes_items"]:
                    clothes_candidates.append({
                        "frame": frame_path,
                        "description": item.get("description", ""),
                        "category": item.get("category", "其他"),
                        "color": item.get("color", "未知")
                    })
            else:
                # Fallback to older scalar format if model ignores schema
                clothes_candidates.append({
                    "frame": frame_path,
                    "description": analysis.get("clothes_description", ""),
                    "category": analysis.get("detected_category", "其他"),
                    "color": analysis.get("detected_color", "未知")
                })
        # ── ACTORS ──
        # Actor extraction has been removed per user request.

        # ── SCENES ──
        if scene_count < MAX_SCENES and analysis.get("has_clear_scene"):
            desc_raw = analysis.get("scene_description", "scene")
            desc = desc_raw.replace(" ", "_")[:80]
            file_name = f"{frame_path.stem}_{desc}.jpg"
            target = workspace["scenes"] / file_name
            shutil.copy2(frame_path, target)
            rel_path = f"/data/{target.relative_to(DATA_DIR)}"
            add_asset_to_vector_store("scenes", target.stem, desc_raw, rel_path)
            sid = upsert_scene(rel_path, desc_raw, video_id)
            scene_ids.append(sid)
            scene_count += 1
            print(f"[{video_id}] 🌄 SAVED: {target.name}")

    # ══════════════════════════════════════════════════════════════════════
    # PASS 2: Group by (Category, Color) → Aggregate Angles
    # ══════════════════════════════════════════════════════════════════════
    if clothes_candidates:
        groups = _group_clothes_by_color_category(clothes_candidates)
        print(f"[{video_id}] Found {len(groups)} unique product(s) by color/category grouping")

        for group in groups:
            # Aggregate details
            all_descs = [item["description"] for item in group]
            summary_desc = _summarize_clothes_descriptions(all_descs)
            
            # Sort frames by description length (usually contains more visual info)
            best_item = max(group, key=lambda x: len(x["description"]))
            
            # Generate ALL renders for the gallery
            gallery_rel_paths = []
            primary_rel_path = ""
            
            print(f"[{video_id}] 👔 Generating gallery from {len(group)} angles for {best_item['color']} {best_item['category']}...")
            for idx, item in enumerate(group):
                desc_clean = item["description"].replace(" ", "_")[:50]
                stem = f"{item['frame'].stem}_{desc_clean}"
                output = extract_clothes_render(item['frame'], workspace["clothes"], stem, description=item['description'])
                if output:
                    rel = f"/data/{output.relative_to(DATA_DIR)}"
                    gallery_rel_paths.append(rel)
                    if item == best_item or not primary_rel_path:
                        primary_rel_path = rel

            if primary_rel_path:
                add_asset_to_vector_store("clothes", Path(primary_rel_path).stem, summary_desc, primary_rel_path)
                c_cls = classify_clothes(DATA_DIR / primary_rel_path.lstrip("/data/"), summary_desc)
                # Overwrite color/category from our structured pass for consistency
                c_cls["color"] = best_item["color"]
                c_cls["category"] = best_item["category"]
                c_cls["source_keyframe"] = f"/data/{best_item['frame'].relative_to(DATA_DIR)}"
                
                cid = upsert_clothes(primary_rel_path, c_cls, summary_desc, video_id)
                # Note: upsert_clothes was updated to handle gallery_urls internally but we can explicitly set it if needed.
                # Since entity_store handles one render at a time, we call it multiple times for each angle.
                for g_path in gallery_rel_paths:
                    if g_path != primary_rel_path:
                        upsert_clothes(g_path, c_cls, summary_desc, video_id)
                
                clothes_ids.append(cid)
                print(f"[{video_id}] 👔 SAVED: {c_cls.get('display_name','')} (with {len(gallery_rel_paths)} angles)")

    print(f"[{video_id}] Summary: {len(clothes_ids)} clothes, {len(actor_ids)} actors, {len(scene_ids)} scenes")
    return {"actor_ids": actor_ids, "clothes_ids": clothes_ids,
            "scene_ids": scene_ids, "thumbnail_url": thumbnail_url}


def _group_clothes_by_color_category(candidates: list[dict]) -> list[list[dict]]:
    """Groups candidates by (category, normalized_color)."""
    COLOR_MAP = {
        "米白": "白色", "米白色": "白色", "纯白": "白色", "奶白": "白色", "象牙白": "白色",
        "炭黑": "黑色", "深黑": "黑色", "墨黑": "黑色",
        "藏蓝": "蓝色", "深蓝": "蓝色", "宝蓝": "蓝色",
        "酒红": "红色", "大红": "红色", "粉色": "红色",
        "咖啡": "棕色", "卡其": "棕色", "驼色": "棕色"
    }
    
    groups = {}
    for item in candidates:
        color = item["color"]
        # Normalize
        norm_color = color
        for k, v in COLOR_MAP.items():
            if k in color:
                norm_color = v
                break
        
        key = (item["category"], norm_color)
        groups.setdefault(key, []).append(item)
    return list(groups.values())


def _summarize_clothes_descriptions(descriptions: list[str]) -> str:
    """Synthesize a single comprehensive product description from multiple angle observations."""
    if not descriptions:
        return ""
    if len(descriptions) == 1:
        return descriptions[0]
        
    import dashscope
    from http import HTTPStatus
    
    prompt = f"""以下是对同一件衣服从不同角度（正面、侧面、背面、细节等）的观察描述。
请将它们汇总成一段专业、流畅的电商产品描述。要求：
1. 包含所有关键特征（如面料、剪裁、装饰细节）。
2. 语言优美，去除重复信息。
3. 保持客观准确。

输入描述清单：
{chr(10).join([f'- {d}' for d in descriptions])}

结果描述（只需返回一段话）："""

    try:
        response = dashscope.Generation.call(
            model='qwen-max', prompt=prompt
        )
        if response.status_code == HTTPStatus.OK:
            return response.output.text.strip()
    except Exception:
        pass
        
    return descriptions[0] # Fallback to longest one usually chosen before

async def background_video_processing(request: IngestionRequest, video_id: str):
    """
    Main pipeline. Creates a post entry linking all extracted entities.
    """
    import json
    from datetime import date
    print(f"[{video_id}] Starting pipeline...")
    workspace = create_video_workspace(video_id)

    print(f"[{video_id}] Step 1: Ingesting media...")
    try:
        import re
        cleaned_url = str(request.url)
        url_match = re.search(r'(https?://[^\s]+)', cleaned_url)
        if url_match:
            cleaned_url = url_match.group(1)
            print(f"[*] Extracted URL from input: {cleaned_url}")
            
        result = await fetch_media(cleaned_url, workspace["base"])
    except Exception as e:
        print(f"[{video_id}] Ingestion error: {e}")
        return

    media_type = result.get("type", "none")
    if media_type == "none":
        print(f"[{video_id}] No media. Aborting.")
        return

    transcript, script_analysis = "", {}

    if media_type == "video":
        video_path = result.get("video_path", workspace["video"])
        print(f"[{video_id}] Step 2: Extracting keyframes...")
        try:
            frames = extract_keyframes(video_path, workspace["keyframes"], frames_per_second=0.5)
        except Exception as e:
            print(f"[{video_id}] Frame extraction error: {e}")
            return
        entity_links = _run_vla_on_frames(frames, workspace, video_id)

        print(f"[{video_id}] Step 3: Audio & transcript...")
        try:
            extract_audio(video_path, workspace["audio"])
        except Exception as e:
            print(f"[{video_id}] Audio error: {e}")
        transcript = transcribe_audio(workspace["audio"]) if workspace["audio"].exists() else ""
        script_analysis = analyze_transcript(transcript)
        with open(workspace["base"] / "script_analysis.json", "w", encoding="utf-8") as f:
            json.dump({"transcript": transcript, "analysis": script_analysis}, f, ensure_ascii=False, indent=2)
        print(f"[{video_id}] Topic: {script_analysis.get('topic', 'N/A')}")

    elif media_type == "images":
        image_paths = result.get("image_paths", [])
        print(f"[{video_id}] Image gallery: {len(image_paths)} images. Mirroring to keyframes...")
        # Copy to keyframes folder with 'time_XX.00s.jpg' format for timeline
        import shutil
        mirrored_paths = []
        for i, img_path in enumerate(image_paths):
            target = workspace["keyframes"] / f"time_{i*2.0:07.2f}s{img_path.suffix}"
            shutil.copy(img_path, target)
            mirrored_paths.append(target)
            
        entity_links = _run_vla_on_frames(mirrored_paths, workspace, video_id)
    else:
        entity_links = {"actor_ids": [], "clothes_ids": [], "scene_ids": [], "thumbnail_url": ""}

    # ── Post entry linking all entities ──
    date_str = date.today().isoformat()
    base_url = f"/data/{date_str}/{video_id}"
    video_url = f"{base_url}/video.mp4" if media_type == "video" else ""
    
    upsert_post(
        post_id=video_id,
        source_url=str(request.url),
        date=date_str,
        actor_ids=entity_links["actor_ids"],
        clothes_ids=entity_links["clothes_ids"],
        scene_ids=entity_links["scene_ids"],
        transcript=transcript,
        analysis=script_analysis,
        thumbnail_url=entity_links.get("thumbnail_url", ""),
        video_url=video_url
    )
    print(f"[{video_id}] ✓ Post entry: {len(entity_links['actor_ids'])} actors, "
          f"{len(entity_links['clothes_ids'])} clothes, {len(entity_links['scene_ids'])} scenes.")

from threading import Thread

def _run_in_thread(req, vid):
    import asyncio
    asyncio.run(background_video_processing(req, vid))

@app.post("/webhook/openclaw")
async def openclaw_webhook(request: IngestionRequest):
    """
    Webhook endpoint to receive video links from Openclaw.
    It initiates the downloading and processing.
    """
    import re
    cleaned_url = str(request.url)
    url_match = re.search(r'(https?://[^\s]+)', cleaned_url)
    if url_match:
        cleaned_url = url_match.group(1)
        print(f"[*] openclaw_webhook: Extracted URL {cleaned_url}")
        
    video_id = get_video_id(cleaned_url)
    
    # Overwrite request url for downstream functions
    request.url = cleaned_url
    
    # Run in hard background thread to avoid event loop drops
    Thread(target=_run_in_thread, args=(request, video_id), daemon=True).start()
    
    return {
        "status": "processing_started",
        "video_id": video_id,
        "message": "Pipeline started in background thread."
    }

@app.get("/api/assets")
async def get_all_assets():
    """Returns deduplicated asset counts from the entity store (not raw file scan)."""
    from services.entity_store import get_all_actors, get_all_clothes, get_all_scenes
    actors = get_all_actors()
    clothes = get_all_clothes()
    scenes = get_all_scenes()
    return {
        "actors": [{"id": a["actor_id"], "url": a.get("cutout_url", ""), "date": a.get("created_at", "")[:10],
                     "display_name": a.get("display_name", ""), "source_keyframe": a.get("source_keyframe", "")} for a in actors],
        "clothes": [{"id": c["clothes_id"], "url": c.get("render_url", ""), "date": c.get("created_at", "")[:10],
                      "display_name": c.get("display_name", ""), "description": c.get("description", ""),
                      "source_keyframe": c.get("source_keyframe", "")} for c in clothes],
        "scenes": [{"id": s["scene_id"], "url": s.get("scene_url", ""), "date": s.get("created_at", "")[:10],
                     "description": s.get("description", "")} for s in scenes]
    }

@app.get("/api/videos/{video_id}")
async def get_video_details(video_id: str):
    """
    Returns the comprehensive original and extracted assets for a single video.
    Uses the entity store to provide deduplicated and consolidated data.
    """
    from services.entity_store import get_post, get_actor, get_clothes, get_scene
    
    post = get_post(video_id)
    if not post:
        raise HTTPException(status_code=404, detail=f"Post {video_id} not found in store")
        
    # Read assets from entity store — map to frontend format {id, url, display_name}
    assets = {"actors": [], "clothes": [], "scenes": [], "keyframes": []}
    
    # ── ACTORS ──
    for aid in post.get("actor_ids", []):
        actor = get_actor(aid)
        if actor:
            assets["actors"].append({
                "id": actor.get("actor_id", aid),
                "url": actor.get("cutout_url", ""),
                "display_name": actor.get("display_name", ""),
                "created_at": actor.get("created_at", "")
            })
            
    # ── CLOTHES (deduplicated) ──
    seen_clothes = set()
    for cid in post.get("clothes_ids", []):
        if cid in seen_clothes: continue
        clothes = get_clothes(cid)
        if clothes:
            assets["clothes"].append({
                "id": clothes.get("clothes_id", cid),
                "url": clothes.get("render_url", ""),
                "display_name": clothes.get("display_name", ""),
                "description": clothes.get("description", ""),
                "gallery_urls": clothes.get("gallery_urls", []),
                "created_at": clothes.get("created_at", "")
            })
            seen_clothes.add(cid)
            
    # ── SCENES ──
    for sid in post.get("scene_ids", []):
        scene = get_scene(sid)
        if scene:
            assets["scenes"].append({
                "id": scene.get("scene_id", sid),
                "url": scene.get("scene_url", ""),
                "display_name": scene.get("description", "")[:30] + "…" if scene.get("description", "") else "",
                "created_at": scene.get("created_at", "")
            })

    # ── KEYFRAMES ──
    date_str = post.get("date", "")
    video_folder = DATA_DIR / date_str / video_id
    if video_folder.exists():
        kf_dir = video_folder / "keyframes"
        if kf_dir.exists():
            for img in sorted(kf_dir.glob("*.jpg")):
                assets["keyframes"].append({
                    "id": img.stem,
                    "url": f"/data/{date_str}/{video_id}/keyframes/{img.name}"
                })

    return {
        "video_id": video_id,
        "date": date_str,
        "video_url": post.get("video_url"),
        "audio_url": post.get("audio_url"),
        "script_analysis": {
            "summary": post.get("summary", ""),
            "topic": post.get("topic", ""),
            "selling_points": post.get("selling_points", []),
            "tone": post.get("tone", ""),
            "transcript": post.get("transcript", "")
        },
        "assets": assets
    }

from pydantic import BaseModel

class SearchRequest(BaseModel):
    category: str
    query: str
    top_k: int = 10

@app.post("/api/search")
async def search_assets_endpoint(request: SearchRequest):
    """Semantic vector search endpoint."""
    from services.vector_store import search_assets as vs_search
    if request.category not in ["actors", "clothes", "scenes"]:
        raise HTTPException(status_code=400, detail="Invalid category")
    results = vs_search(request.category, request.query, request.top_k)
    return {"results": results}

# ─── Knowledge Base Endpoints ────────────────────────────────────────────────

from fastapi import Response

@app.get("/api/posts")
async def get_all_posts_endpoint(response: Response):
    """Returns all post entries with entity links — the Knowledge Base table data."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    from services.entity_store import get_all_posts, get_actor, get_clothes, get_scene
    posts = get_all_posts()
    # Enrich each post with display info for its linked entities
    enriched = []
    for post in posts:
        actors_info = [get_actor(aid) for aid in post.get("actor_ids", []) if get_actor(aid)]
        clothes_info = [get_clothes(cid) for cid in post.get("clothes_ids", []) if get_clothes(cid)]
        scene_info   = [get_scene(sid) for sid in post.get("scene_ids", []) if get_scene(sid)]
        enriched.append({**post, "actors_info": actors_info,
                         "clothes_info": clothes_info, "scenes_info": scene_info})
    return {"posts": enriched}

@app.get("/api/entities/{entity_type}")
async def get_entities(entity_type: str):
    """Returns all entities of a given type: actors | clothes | scenes."""
    from services.entity_store import get_all_actors, get_all_clothes, get_all_scenes
    if entity_type == "actors":
        return {"entities": get_all_actors()}
    elif entity_type == "clothes":
        return {"entities": get_all_clothes()}
    elif entity_type == "scenes":
        return {"entities": get_all_scenes()}
    raise HTTPException(status_code=400, detail=f"Unknown entity type: {entity_type}")

from pydantic import BaseModel

class ClothesUpdate(BaseModel):
    display_name: str | None = None
    category: str | None = None
    style_class: str | None = None
    color: str | None = None

@app.put("/api/entities/clothes/{entity_id}")
async def update_clothes_endpoint(entity_id: str, updates: ClothesUpdate):
    from services.entity_store import update_clothes
    
    update_dict = {k: v for k, v in updates.dict().items() if v is not None}
    if not update_dict:
        return {"status": "success", "message": "No changes provided"}
        
    result = update_clothes(entity_id, update_dict)
    if result:
        return {"status": "success", "entity": result}
    raise HTTPException(status_code=404, detail="Clothing entity not found")

@app.delete("/api/entities/{entity_type}/{entity_id}")
async def delete_entity_endpoint(entity_type: str, entity_id: str):
    from services.entity_store import delete_actor, delete_clothes, delete_scene
    
    success = False
    if entity_type == "actors":
        success = delete_actor(entity_id)
    elif entity_type == "clothes":
        success = delete_clothes(entity_id)
    elif entity_type == "scenes":
        success = delete_scene(entity_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown entity type: {entity_type}")
        
    if success:
        return {"status": "success", "message": f"{entity_type} entity deleted"}
    raise HTTPException(status_code=404, detail="Entity not found")


@app.get("/api/entities/{entity_type}/{entity_id}")
async def get_entity_detail(entity_type: str, entity_id: str):
    """Returns a single entity with all posts it appeared in."""
    from services.entity_store import get_actor, get_clothes, get_scene, get_post
    entity = None
    if entity_type == "actors":   entity = get_actor(entity_id)
    elif entity_type == "clothes": entity = get_clothes(entity_id)
    elif entity_type == "scenes":  entity = get_scene(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    # Attach post summaries
    posts = [get_post(pid) for pid in entity.get("appeared_in", []) if get_post(pid)]
    return {**entity, "posts": posts}

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serves the main application UI."""
    try:
        with open("frontend/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "UI not found. Please build the frontend."

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
