import os
import json
import time
import asyncio
import requests
from pathlib import Path

COMFY_API_URL = os.getenv("COMFY_API_URL", "http://127.0.0.1:8188")
WORKFLOW_FILE = Path(__file__).parent.parent / "flux_4090_optimized.json"

async def generate_product_photo_async(frame_path: Path, dest_path: Path, description: str = "") -> Path | None:
    """
    Generates a clean e-commerce product photo by calling the local ComfyUI API.
    Uses FLUX.1 optimized for 4090 (FP8) to ensure consistency and performance.
    """
    if not WORKFLOW_FILE.exists():
        print(f"[Generator] Error: Workflow file not found at {WORKFLOW_FILE}")
        return None

    try:
        # 1. Prepare Request to ComfyUI
        with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
            workflow = json.load(f)

        # Update prompt and image path in workflow
        prompt_text = (
            f"A professional e-commerce product photo of {description or 'a garment'}, "
            f"isolated on a pure white flat-lay background. High resolution, studio lighting, "
            f"visible fabric texture, clean edges."
        )
        
        # ComfyUI LoadImage node (ID 10) can take absolute paths if configured
        workflow["10"]["inputs"]["image"] = str(frame_path.absolute())
        workflow["6"]["inputs"]["text"] = prompt_text

        # 2. Queue Prompt
        print(f"[Generator] Sending request to local ComfyUI at {COMFY_API_URL}")
        response = requests.post(f"{COMFY_API_URL}/prompt", json={"prompt": workflow})
        
        if response.status_code != 200:
            print(f"[Generator] ComfyUI Error: {response.text}")
            return None
        
        prompt_id = response.json().get("prompt_id")
        print(f"[Generator] Queued successfully. Prompt ID: {prompt_id}")

        # 3. Poll for completion
        start_time = time.time()
        timeout = 300  # 5 minutes for FLUX
        
        while time.time() - start_time < timeout:
            history_url = f"{COMFY_API_URL}/history/{prompt_id}"
            hist_resp = requests.get(history_url)
            
            if hist_resp.status_code == 200:
                history = hist_resp.json()
                if prompt_id in history:
                    # Found finished task
                    outputs = history[prompt_id].get("outputs", {})
                    # Node "9" is our SaveImage
                    if "9" in outputs and "images" in outputs["9"]:
                        image_info = outputs["9"]["images"][0]
                        
                        # Fetch the image via /view API
                        view_url = f"{COMFY_API_URL}/view?filename={image_info['filename']}&subfolder={image_info['subfolder']}&type={image_info['type']}"
                        img_data = requests.get(view_url).content
                        
                        with open(dest_path, "wb") as f:
                            f.write(img_data)
                        
                        print(f"[Generator] ✓ Successfully saved generated product to {dest_path.name}")
                        return dest_path
            
            await asyncio.sleep(2)
            
        print("[Generator] Timeout waiting for ComfyUI.")
        return None

    except Exception as e:
        print(f"[Generator] Failed to call local ComfyUI: {e}")
        return None

def generate_product_photo(frame_path: Path, dest_path: Path, description: str = "") -> Path | None:
    """Synchronous wrapper for main pipeline integration"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        import threading
        result = None
        def _run():
            nonlocal result
            try:
                result = asyncio.run(generate_product_photo_async(frame_path, dest_path, description))
            except Exception as ex:
                print(f"[Generator] Thread error: {ex}")
        t = threading.Thread(target=_run)
        t.start()
        t.join()
        return result
    else:
        return asyncio.run(generate_product_photo_async(frame_path, dest_path, description))
