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

def generate_video_prompt(topic: str, original_descs: list[str], clothes_descs: list[str], scenes_descs: list[str]) -> str:
    """
    Generates a high-quality video generation prompt for tools like Sora/Runway
    based on the extracted product information.
    """
    import os
    import dashscope
    from http import HTTPStatus
    
    dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

    prompt = f"""
    Please act as an expert AI Video Generation Prompt Engineer (like for Sora, Runway Gen-2, or Midjourney).
    I have extracted information from a product video/page. I need you to write a highly detailed, cinematic, and descriptive prompt IN ENGLISH that can be used to generate a similar styled video emphasizing these products.

    Topic/Title: {topic}
    Original Selling Points: {', '.join(original_descs)}
    Extracted Clothing/Products: {', '.join(clothes_descs)}
    Extracted Scenes/Backgrounds: {', '.join(scenes_descs)}

    Your output should JUST be the raw English prompt, without any markdown, explanations, or quotes.
    The prompt should be highly descriptive of the lighting, camera angle, subject, clothing details, and environment.

    Example format: "A cinematic tracking shot of a beautiful model wearing a [clothing details] walking through a [scene details], soft ambient lighting, high fashion, 8k resolution, photorealistic, 35mm lens."
    """
    
    print("[*] Generating Video Generation Prompt with Qwen-Max...")
    
    try:
        response = dashscope.Generation.call(
            model='qwen-max',
            messages=[{'role': 'user', 'content': prompt}],
            result_format='message'
        )
        
        if response.status_code == HTTPStatus.OK:
            content = response.output.choices[0].message.content
            return content.strip()
        else:
            print(f"[-] LLM Error generating video prompt: {response.message}")
            return ""
            
    except Exception as e:
        print(f"[-] LLM Video Prompt Exception: {e}")
        return ""
