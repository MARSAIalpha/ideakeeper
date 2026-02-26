import os
import json
from pathlib import Path
from http import HTTPStatus
import dashscope

# https://help.aliyun.com/zh/dashscope/developer-reference/qwen-vl-api
# Ensure you set DASHSCOPE_API_KEY in your environment
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

def analyze_frame(image_path: Path) -> dict:
    """
    Analyzes an extracted keyframe using Qwen-VL.
    Identifies whether it's a good shot for an Actor, Clothes, or Scene.
    Returns a dictionary of boolean flags and descriptions.
    """
    if not dashscope.api_key or dashscope.api_key == "your_vlm_api_key_here":
        # Fallback simulated response for testing without an API key
        print(f"[*] Simulated Qwen-VL analysis for {image_path.name}")
        return {
            "has_clear_actor": True,
            "has_clear_clothes": True,
            "has_clear_scene": False,
            "actor_description": "model",
            "clothes_description": "outfit",
            "scene_description": ""
        }

    # Qwen-VL can accept local file paths directly via file:// prefix
    local_image_path = f"file://{image_path.absolute()}"

    prompt = """
    你是一位专业的时尚电商视觉分析师。这张图片来自服装/时尚视频或照片帖子。
    请仔细分析图片。如果图片中出现了**多套完全不同的衣服**，你必须严格把它们拆分开来，绝不能合并成一个描述！
    
    1. 服装产品（最高优先级）：是否有清晰、光线充足的服装单品？
       - 如果有多个模特穿着不同的衣服，或者一个模特穿着内外不同的单品，请将**每一件**独立的、清晰可辨认的衣物（如分别的上衣、裤子、连衣裙等）分离出来。
       - 把它们作为独立的项目记录在 "clothes_items" 数组里。绝不要在一个 description 里写两件衣服（例如严禁"白色长裙与黄色短裙"）。
       - 针对每一件单品，详细描述：颜色、面料质感、款式（如"亮黄色纯棉挂脖短裙"）。
    
    2. 场景/背景：是否适合视频制作使用？
    
    请只返回原始JSON对象（不要markdown标记，不要代码块）：
    {
        "has_clear_clothes": true/false,
        "clothes_items": [
            {
                "description": "单件衣物的纯粹外观描述，确保只描述一件单品",
                "category": "品类如：连衣裙/外套/T恤/裤子/半身裙",
                "color": "主色调如：白色/黑色/黄色"
            }
        ],
        "has_clear_scene": true/false,
        "scene_description": "场景的中文描述，没有则为空字符串"
    }
    """
    
    messages = [
        {
            "role": "user",
            "content": [
                {"image": local_image_path},
                {"text": prompt}
            ]
        }
    ]

    try:
        response = dashscope.MultiModalConversation.call(
            model='qwen-vl-plus',
            messages=messages
        )
        
        if response.status_code == HTTPStatus.OK:
            content = response.output.choices[0].message.content[0].get('text', '')
            # Try to safely parse the JSON, Qwen sometimes wraps in markdown ```json ... ```
            clean_content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_content)
        else:
            print(f"[-] Qwen-VL API Error ({response.code}): {response.message}")
            return {
                "has_clear_actor": False, "has_clear_clothes": False, "has_clear_scene": False,
                "actor_description": "", "clothes_description": "", "scene_description": ""
            }
            
    except Exception as e:
        print(f"[-] VLA Exception on {image_path.name}: {e}")
        return {
            "has_clear_actor": False, "has_clear_clothes": False, "has_clear_scene": False,
            "actor_description": "", "clothes_description": "", "scene_description": ""
        }
