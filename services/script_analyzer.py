import os
from http import HTTPStatus
import dashscope

def analyze_transcript(transcript: str) -> dict:
    """
    Analyzes the video's transcript to extract topics, selling points, and tone.
    Uses qwen-plus text model.
    """
    if not transcript.strip():
        return {
            "topic": "Unknown",
            "selling_points": [],
            "tone": "Unknown",
            "summary": "No speech detected in the video."
        }
        
    dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
    
    prompt = f"""
    Please analyze the following transcript from a short video (like TikTok or Xiaohongshu) and extract the following information. Return the response STRICTLY as a raw JSON string without any markdown formatting.
    
    Structure:
    {{
        "topic": "Main topic or subject of the video",
        "selling_points": ["Point 1", "Point 2"],
        "tone": "The vibe or emotional tone (e.g., energetic, relaxed, professional)",
        "summary": "A 1-2 sentence summary of what is happening or being sold"
    }}
    
    Transcript:
    "{transcript}"
    """
    
    print("[*] Analyzing script logic with Qwen-Plus...")
    
    try:
        response = dashscope.Generation.call(
            model='qwen-plus',
            messages=[{'role': 'user', 'content': prompt}],
            result_format='message'
        )
        
        if response.status_code == HTTPStatus.OK:
            content = response.output.choices[0].message.content
            import json
            # Remove any markdown backticks if qwen returns them despite instructions
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        else:
            print(f"[-] LLM Error: {response.message}")
            return {}
            
    except Exception as e:
        print(f"[-] LLM Analysis Exception: {e}")
        return {}
