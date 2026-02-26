"""
Reprocess existing videos: run VLA analysis + rembg on existing keyframes.
Does NOT re-download videos or re-extract keyframes.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from main import _run_vla_on_frames, DATA_DIR
from services.entity_store import upsert_post

def reprocess_all():
    date_dirs = sorted(DATA_DIR.glob("20*"))
    for date_dir in date_dirs:
        date_str = date_dir.name
        for video_dir in sorted(date_dir.iterdir()):
            if not video_dir.is_dir():
                continue
            video_id = video_dir.name
            if video_id.startswith("test_"):
                continue
            
            kf_dir = video_dir / "keyframes"
            if not kf_dir.exists():
                print(f"[{video_id}] No keyframes dir, skipping")
                continue
            
            frames = sorted(kf_dir.glob("*.jpg")) + sorted(kf_dir.glob("*.png"))
            if not frames:
                print(f"[{video_id}] No keyframes found, skipping")
                continue
            
            # Build workspace dict
            workspace = {
                "base": video_dir,
                "keyframes": kf_dir,
                "actors": video_dir / "actors",
                "clothes": video_dir / "clothes",
                "scenes": video_dir / "scenes",
                "video": video_dir / "video.mp4",
            }
            workspace["actors"].mkdir(exist_ok=True)
            workspace["clothes"].mkdir(exist_ok=True)
            workspace["scenes"].mkdir(exist_ok=True)
            
            print(f"\n{'='*60}")
            print(f"[{video_id}] Processing {len(frames)} keyframes...")
            print(f"{'='*60}")
            
            result = _run_vla_on_frames(frames, workspace, video_id)
            
            # Read existing script analysis
            sa_file = video_dir / "script_analysis.json"
            transcript = ""
            analysis = {}
            if sa_file.exists():
                try:
                    sa = json.loads(sa_file.read_text())
                    transcript = sa.get("transcript", "")
                    analysis = sa.get("analysis", {})
                except Exception:
                    pass
            
            video_url = ""
            if workspace["video"].exists():
                video_url = f"/data/{workspace['video'].relative_to(DATA_DIR)}"
            
            upsert_post(
                post_id=video_id,
                source_url="",
                date=date_str,
                video_url=video_url,
                thumbnail_url=result.get("thumbnail_url", ""),
                actor_ids=result.get("actor_ids", []),
                clothes_ids=result.get("clothes_ids", []),
                scene_ids=result.get("scene_ids", []),
                transcript=transcript,
                analysis=analysis,
            )
            
            print(f"[{video_id}] ✓ Done: {len(result.get('clothes_ids',[]))} clothes, "
                  f"{len(result.get('actor_ids',[]))} actors, "
                  f"{len(result.get('scene_ids',[]))} scenes")

if __name__ == "__main__":
    reprocess_all()
