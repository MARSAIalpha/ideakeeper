import ffmpeg
import os
from pathlib import Path

def extract_keyframes(video_path: Path, output_dir: Path, frames_per_second: float = 1.0) -> list[Path]:
    """
    Extracts keyframes from the video at a given frame rate (default 1 frame every 2 seconds).
    Returns a list of saved image paths.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found at {video_path}")
        
    print(f"[*] Extracting keyframes to {output_dir}")
    # Using ffmpeg-python to extract frames. 
    # To get accurate timestamps in filenames, we use a more complex output pattern or calculate it.
    # Here we stick to a simple strategy: extract at fixed intervals and name them by their sequence.
    # However, to support 'seconds' in filenames, we'll use the 'select' filter and segmenting logic
    # or just rename them after extraction based on the known FPS.
    
    interval = 1.0 / frames_per_second # e.g. 0.5 fps -> 2.0s interval
    
    try:
        (
            ffmpeg
            .input(str(video_path))
            .filter('fps', fps=frames_per_second)
            .output(f"{output_dir}/frame_%04d.jpg", **{'qscale:v': 2}) 
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        # Rename frames to include seconds for easier frontend handling
        extracted = sorted(list(output_dir.glob("frame_*.jpg")))
        renamed_paths = []
        for i, path in enumerate(extracted):
            seconds = i * interval
            new_name = f"time_{seconds:07.2f}s.jpg"
            new_path = path.parent / new_name
            path.rename(new_path)
            renamed_paths.append(new_path)
            
        print(f"[*] Extracted and timestamped {len(renamed_paths)} keyframes.")
        return renamed_paths
        
    except ffmpeg.Error as e:
        print('stdout:', e.stdout.decode('utf8'))
        print('stderr:', e.stderr.decode('utf8'))
        raise e

