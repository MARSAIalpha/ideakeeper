import ffmpeg
import os
from pathlib import Path

def extract_audio(video_path: Path, output_audio_path: Path) -> Path:
    """
    Extracts the audio track from a video and saves it as an MP3 file.
    Returns the path to the extracted audio file.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found at {video_path}")
        
    print(f"[*] Extracting audio from {video_path.name} to {output_audio_path.name}")
    try:
        (
            ffmpeg
            .input(str(video_path))
            .output(str(output_audio_path), format='mp3', acodec='libmp3lame', audio_bitrate='128k')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        print('[-] FFmpeg Audio Extraction stdout:', e.stdout.decode('utf8'))
        print('[-] FFmpeg Audio Extraction stderr:', e.stderr.decode('utf8'))
        raise e
        
    return output_audio_path
