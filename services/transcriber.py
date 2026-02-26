import os
from pathlib import Path
from http import HTTPStatus
import dashscope

def transcribe_audio(audio_path: Path) -> str:
    """
    Uses Dashscope Paraformer (paraformer-v1) to convert audio to a text string.
    Dashscope API expects the audio file to be accessible or uploaded.
    Since Dashscope Python SDK supports local paths via 'file://', we use it here.
    """
    dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
    if not dashscope.api_key:
        print("[-] No DASHSCOPE_API_KEY set. Skipping transcription.")
        return ""
        
    print(f"[*] Transcribing audio file {audio_path.name}...")
    
    local_audio_url = f"file://{audio_path.absolute()}"
    
    try:
        # ASR call - using the standard paraformer model 
        task_response = dashscope.audio.asr.Transcription.async_call(
            model='paraformer-v1',
            file_urls=[local_audio_url]
        )
        
        # dashscope ASR is asynchronous. We wait for it to complete.
        transcribe_response = dashscope.audio.asr.Transcription.wait(task=task_response.output.task_id)
        
        if transcribe_response.status_code == HTTPStatus.OK:
            results = transcribe_response.output.get("results", [])
            if not results:
                return ""
                
            # Combine sentences from the result
            transcript = []
            for item in results:
                transcript_text = item.get("subtask_result", {}).get("text", "")
                if transcript_text:
                    transcript.append(transcript_text)
                    
            return " ".join(transcript)
        else:
            print(f"[-] ASR Error: {transcribe_response.message}")
            return ""
            
    except Exception as e:
        print(f"[-] Transcription Exception: {e}")
        return ""
