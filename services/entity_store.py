"""
services/entity_store.py

JSON-backed relational entity store.
Manages four entity types:
  - posts   → one per ingested URL, links to entity IDs
  - actors  → classified person entities
  - clothes → classified clothing entities
  - scenes  → background scene entities

All data is persisted to data/entities/*.json files.
Deduplication uses the entity's display_name + style_class as a key.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime

from services.storage import DATA_DIR

ENTITY_DIR = DATA_DIR / "entities"
ENTITY_DIR.mkdir(parents=True, exist_ok=True)

POSTS_FILE   = ENTITY_DIR / "posts.json"
ACTORS_FILE  = ENTITY_DIR / "actors.json"
CLOTHES_FILE = ENTITY_DIR / "clothes.json"
SCENES_FILE  = ENTITY_DIR / "scenes.json"


def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}

def _save(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────
#  ACTOR ENTITIES
# ─────────────────────────────────────────────

def upsert_actor(cutout_url: str, classification: dict, post_id: str) -> str:
    """
    Insert or update an actor entity. Returns the actor_id.
    Deduplicates by display_name (celebrity name or style class).
    """
    actors = _load(ACTORS_FILE)
    display_name = classification.get("display_name", "Other")

    # Find existing entity with same display_name
    existing_id = None
    for aid, a in actors.items():
        if a.get("display_name") == display_name:
            existing_id = aid
            break

    if existing_id:
        actor = actors[existing_id]
        # Add post reference
        if post_id not in actor.get("appeared_in", []):
            actor.setdefault("appeared_in", []).append(post_id)
        # Update cutout if not set
        if not actor.get("cutout_url"):
            actor["cutout_url"] = cutout_url
        actors[existing_id] = actor
        _save(ACTORS_FILE, actors)
        return existing_id
    else:
        actor_id = hashlib.md5(display_name.encode()).hexdigest()[:10]
        actors[actor_id] = {
            "actor_id": actor_id,
            "display_name": display_name,
            "celebrity_name": classification.get("celebrity_name"),
            "style_class": classification.get("style_class", "Other"),
            "cutout_url": cutout_url,
            "source_keyframe": classification.get("source_keyframe", ""),
            "appeared_in": [post_id],
            "created_at": datetime.now().isoformat()
        }
        _save(ACTORS_FILE, actors)
        return actor_id


def get_all_actors() -> list:
    return list(_load(ACTORS_FILE).values())

def get_actor(actor_id: str) -> dict | None:
    return _load(ACTORS_FILE).get(actor_id)

def delete_actor(actor_id: str) -> bool:
    actors = _load(ACTORS_FILE)
    if actor_id in actors:
        del actors[actor_id]
        _save(ACTORS_FILE, actors)
        return True
    return False

# ─────────────────────────────────────────────
#  CLOTHES ENTITIES
# ─────────────────────────────────────────────

def upsert_clothes(render_url: str, classification: dict, description: str, post_id: str, clothes_id: str = None) -> str:
    """
    Insert or update a clothes entity. Returns the clothes_id.
    Deduplicates by category + style_class + color combination OR by explicit clothes_id.
    Accumulates render_urls into gallery_urls.
    """
    clothes = _load(CLOTHES_FILE)
    
    if clothes_id:
        # If an explicit ID is provided, we ONLY update that ID if it exists.
        # Otherwise, we create a new entry with this ID.
        existing_id = clothes_id if clothes_id in clothes else None
    else:
        # Fallback to dedup key ONLY if no explicit ID was provided
        key = f"{classification.get('category')}_{classification.get('style_class')}_{classification.get('color')}"
        existing_id = None
        for cid, c in clothes.items():
            if c.get("dedup_key") == key:
                existing_id = cid
                break
        
        if not existing_id:
            clothes_id = hashlib.md5(key.encode()).hexdigest()[:10]

    display_name = classification.get('display_name', f"{classification.get('color', '')} {classification.get('category', 'Clothes')} ({classification.get('style_class', '')})")

    if existing_id:
        c = clothes[existing_id]
        if post_id not in c.get("appeared_in", []):
            c.setdefault("appeared_in", []).append(post_id)
        
        # Accumulate in gallery
        gallery = c.get("gallery_urls", [])
        if not gallery and c.get("render_url"):
            gallery = [c["render_url"]]
        
        if render_url and render_url not in gallery:
            gallery.append(render_url)
        c["gallery_urls"] = gallery
        
        # If the main render_url is missing, set it
        if not c.get("render_url") and render_url:
            c["render_url"] = render_url
            
        if classification.get("attributes"):
            c["attributes"] = classification["attributes"]
            
        clothes[existing_id] = c
        _save(CLOTHES_FILE, clothes)
        return existing_id
    else:
        new_entry = {
            "clothes_id": clothes_id,
            "display_name": display_name,
            "dedup_key": f"{classification.get('category')}_{classification.get('style_class')}_{classification.get('color')}",
            "category": classification.get("category", "Other"),
            "style_class": classification.get("style_class", "Other"),
            "color": classification.get("color", "Unknown"),
            "description": description,
            "render_url": render_url,
            "gallery_urls": [render_url] if render_url else [],
            "source_keyframe": classification.get("source_keyframe", ""),
            "appeared_in": [post_id],
            "created_at": datetime.now().isoformat()
        }
        if classification.get("attributes"):
            new_entry["attributes"] = classification["attributes"]
            
        clothes[clothes_id] = new_entry
        _save(CLOTHES_FILE, clothes)
        return clothes_id

def get_all_clothes() -> list:
    return list(_load(CLOTHES_FILE).values())

def get_clothes(clothes_id: str) -> dict | None:
    return _load(CLOTHES_FILE).get(clothes_id)

def update_clothes(clothes_id: str, updates: dict) -> dict | None:
    clothes = _load(CLOTHES_FILE)
    if clothes_id in clothes:
        clothes[clothes_id].update(updates)
        _save(CLOTHES_FILE, clothes)
        return clothes[clothes_id]
    return None

def delete_clothes(clothes_id: str) -> bool:
    clothes = _load(CLOTHES_FILE)
    if clothes_id in clothes:
        del clothes[clothes_id]
        _save(CLOTHES_FILE, clothes)
        return True
    return False


# ─────────────────────────────────────────────
#  SCENE ENTITIES
# ─────────────────────────────────────────────

def upsert_scene(scene_url: str, description: str, post_id: str) -> str:
    scenes = _load(SCENES_FILE)
    scene_id = hashlib.md5((scene_url + post_id).encode()).hexdigest()[:10]
    if scene_id not in scenes:
        scenes[scene_id] = {
            "scene_id": scene_id,
            "description": description,
            "scene_url": scene_url,
            "appeared_in": [post_id],
            "created_at": datetime.now().isoformat()
        }
    else:
        s = scenes[scene_id]
        if post_id not in s.get("appeared_in", []):
            s.setdefault("appeared_in", []).append(post_id)
        scenes[scene_id] = s
    _save(SCENES_FILE, scenes)
    return scene_id


def get_all_scenes() -> list:
    return list(_load(SCENES_FILE).values())

def get_scene(scene_id: str) -> dict | None:
    return _load(SCENES_FILE).get(scene_id)

def delete_scene(scene_id: str) -> bool:
    scenes = _load(SCENES_FILE)
    if scene_id in scenes:
        del scenes[scene_id]
        _save(SCENES_FILE, scenes)
        return True
    return False

# ─────────────────────────────────────────────
#  POST ENTRIES
# ─────────────────────────────────────────────

def upsert_post(post_id: str, source_url: str, date: str,
                actor_ids: list, clothes_ids: list, scene_ids: list,
                transcript: str, analysis: dict, thumbnail_url: str = "",
                video_url: str = ""):
    posts = _load(POSTS_FILE)

    topic = analysis.get("topic", "") if analysis else ""
    selling_points = analysis.get("selling_points", []) if analysis else []
    tone = analysis.get("tone", "") if analysis else ""
    summary = analysis.get("summary", "") if analysis else ""

    posts[post_id] = {
        "post_id": post_id,
        "source_url": source_url,
        "date": date,
        "thumbnail_url": thumbnail_url,
        "actor_ids": actor_ids,
        "clothes_ids": clothes_ids,
        "scene_ids": scene_ids,
        "video_url": video_url,
        "transcript": transcript,
        "topic": topic,
        "selling_points": selling_points,
        "tone": tone,
        "summary": summary,
        "updated_at": datetime.now().isoformat()
    }
    _save(POSTS_FILE, posts)


def get_all_posts() -> list:
    return list(_load(POSTS_FILE).values())

def get_post(post_id: str) -> dict | None:
    return _load(POSTS_FILE).get(post_id)
