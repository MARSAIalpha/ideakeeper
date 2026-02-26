import os
from datetime import datetime
from pathlib import Path

# Base data directory where all videos and extracted assets are stored
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))

def get_daily_folder() -> Path:
    """Returns the path for physical storage, organized by date."""
    today = datetime.now().strftime("%Y-%m-%d")
    folder_path = DATA_DIR / today
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path

def create_video_workspace(video_id: str) -> dict:
    """
    Creates a dedicated folder structure for a processed video.
    Returns paths to each sub-directory.
    """
    daily_folder = get_daily_folder()
    video_folder = daily_folder / video_id
    
    # Subdirectories for different assets
    paths = {
        "base": video_folder,
        "video": video_folder / "video.mp4",
        "audio": video_folder / "audio.mp3",
        "keyframes": video_folder / "keyframes",
        "actors": video_folder / "actors",
        "clothes": video_folder / "clothes",
        "scenes": video_folder / "scenes",
    }
    
    for key, path in paths.items():
        if key not in ["base", "video", "audio"]:
            path.mkdir(parents=True, exist_ok=True)
            
    return paths

def save_file(path: Path, content: bytes):
    """Utility to quickly save byte content to a file."""
    with open(path, 'wb') as f:
        f.write(content)
