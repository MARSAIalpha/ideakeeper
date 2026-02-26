"""
services/segmenter.py

Product image generation pipeline for clothes and actor assets.

Strategy (in order of priority):
1. Qwen-Image-2.0 image editing: sends the original keyframe as reference
   and generates a clean e-commerce product photo preserving the actual garment.
2. rembg background removal: extracts the foreground from the original frame.
3. Fallback: saves the original frame as a PNG.
"""

from pathlib import Path
from PIL import Image
import io

from .generator import generate_product_photo

try:
    from rembg import remove as rembg_remove
    HAS_REMBG = True
except ImportError:
    HAS_REMBG = False
    print("[segmenter] 警告: rembg未安装，将使用原图作为备选。")


def _remove_background(input_path: Path, output_path: Path) -> bool:
    """使用rembg去除背景，成功返回True。"""
    if not HAS_REMBG:
        return False
    try:
        with open(input_path, "rb") as f:
            input_data = f.read()
        result = rembg_remove(input_data)
        img = Image.open(io.BytesIO(result)).convert("RGBA")
        img.save(str(output_path), format="PNG")
        print(f"[rembg] ✓ 背景已去除: {output_path.name}")
        return True
    except Exception as e:
        print(f"[rembg] 错误: {e}")
        return False


def extract_clothes_render(frame_path: Path, dest_dir: Path, filename_stem: str,
                           description: str = "") -> Path | None:
    """
    从视频关键帧中提取服装产品图。
    
    优先使用 Qwen-Image-2.0 图生图，将人物身上的衣服生成为电商产品图。
    如果 AI 生成失败，降级使用 rembg 背景去除。
    最后兜底保存原图。
    """
    output_path = dest_dir / f"{filename_stem}.png"
    
    # 1. 尝试 Qwen-Image-2.0 图生图产品图
    result = generate_product_photo(frame_path, output_path, description)
    if result:
        return result
    
    # 2. 降级: rembg 背景去除
    print(f"[segmenter] AI生成失败，降级使用rembg...")
    if _remove_background(frame_path, output_path):
        return output_path
    
    # 3. 兜底: 保存原图
    try:
        img = Image.open(frame_path).convert("RGBA")
        img.save(str(output_path), format="PNG")
        print(f"[segmenter] 兜底（原图）: {output_path.name}")
        return output_path
    except Exception:
        return None



