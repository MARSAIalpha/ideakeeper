"""
services/classifier.py

使用 Qwen-VL 将演员和服装分类为有意义的中文标签。

演员分类：
  - 如果是公认的名人 → 返回其中文名字
  - 否则 → 风格分类

服装分类：
  - 品类 + 风格 + 颜色 + 中文展示名
"""

import os
import json
from pathlib import Path
from http import HTTPStatus
import dashscope

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

ACTOR_STYLES = [
    "酷女孩", "宫廷风", "现代时尚", "街头风",
    "商务风", "复古风", "运动风", "甜美风", "极简风", "其他"
]

CLOTHES_CATEGORIES = [
    "连衣裙", "夹克", "大衣", "衬衫", "T恤", "裤子", "半裙",
    "短裤", "西装", "针织衫", "运动服", "配饰", "其他"
]

CLOTHES_STYLES = [
    "现代时尚", "极简风", "宫廷风", "街头风", "商务风",
    "复古风", "甜美风", "运动风", "前卫风", "其他"
]


def classify_actor(image_path: Path, vla_description: str) -> dict:
    """
    分析人物图片并进行分类：
    - celebrity_name: 如果是公众人物，返回中文名；否则为null
    - style_class: 风格分类
    - display_name: 名人名字或风格分类
    """
    local_path = f"file://{image_path.absolute()}"

    prompt = f"""请分析这张人物图片，回答以下两个问题：

1. 名人识别：这个人是否是知名的中国或国际明星、演员或公众人物？
   - 如果是，请提供其最常用的中文名字（如：刘亦菲、范冰冰、杨幂）
   - 如果不是，填写 null

2. 风格分类：从以下选项中选择最匹配的风格：
   {', '.join(ACTOR_STYLES)}

参考描述：{vla_description}

请只返回原始JSON（不要markdown标记）：
{{
    "celebrity_name": "中文名字" 或 null,
    "style_class": "上述风格选项之一"
}}"""

    messages = [{"role": "user", "content": [{"image": local_path}, {"text": prompt}]}]

    try:
        response = dashscope.MultiModalConversation.call(
            model='qwen-vl-plus', messages=messages
        )
        if response.status_code == HTTPStatus.OK:
            text = response.output.choices[0].message.content[0].get('text', '{}')
            clean = text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            celeb = result.get("celebrity_name")
            style = result.get("style_class", "其他")
            return {
                "celebrity_name": celeb,
                "style_class": style,
                "display_name": celeb if celeb else style
            }
    except Exception as e:
        print(f"[-] 演员分类错误: {e}")

    return {"celebrity_name": None, "style_class": "其他", "display_name": "其他"}


def classify_clothes(image_path: Path, vla_description: str) -> dict:
    """
    分析服装图片并进行分类：
    - category: 服装品类
    - style_class: 时尚风格
    - color: 主色调
    - display_name: 专业中文标签
    """
    local_path = f"file://{image_path.absolute()}"

    prompt = f"""请分析这张服装产品图片，进行以下分类：

1. 品类（选一个）：{', '.join(CLOTHES_CATEGORIES)}
2. 风格（选一个）：{', '.join(CLOTHES_STYLES)}
3. 颜色：主色调（用中文描述，如：米白色、深蓝色、暖棕色、黑色）
4. 展示名称：专业的中文产品名称，结合颜色和品类（如："黑色丝绒长裙"、"米白西装外套"、"深蓝色风衣"）

VLA描述参考：{vla_description}

请只返回原始JSON（不要markdown标记）：
{{
    "category": "品类选项之一",
    "style_class": "风格选项之一",
    "color": "中文颜色描述",
    "display_name": "专业中文产品名称"
}}"""

    messages = [{"role": "user", "content": [{"image": local_path}, {"text": prompt}]}]

    try:
        response = dashscope.MultiModalConversation.call(
            model='qwen-vl-plus', messages=messages
        )
        if response.status_code == HTTPStatus.OK:
            text = response.output.choices[0].message.content[0].get('text', '{}')
            clean = text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            
            dname = result.get("display_name")
            if not dname:
                dname = f"{result.get('color', '')} {result.get('category', '服装')}"
                
            return {
                "category": result.get("category", "其他"),
                "style_class": result.get("style_class", "其他"),
                "color": result.get("color", "未知"),
                "display_name": dname
            }
    except Exception as e:
        print(f"[-] 服装分类错误: {e}")

    return {"category": "其他", "style_class": "其他", "color": "未知", "display_name": "服装单品"}
