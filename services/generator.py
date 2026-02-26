"""
services/generator.py

Uses Playwright to automate Google Gemini Web UI (gemini.google.com) 
for Image-to-Image garment extraction to avoid hallucinations.
"""

import os
import base64
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def generate_product_photo_async(frame_path: Path, dest_path: Path, description: str = "") -> Path | None:
    """
    Generates a clean e-commerce product photo by using Playwright to upload the original video frame
    to Gemini Web (gemini.google.com). This avoids hallucinations by doing explicit visual Image-to-Image extraction.
    Ensures safe execution within an existing asyncio loop.
    """
    profile_dir = Path(os.path.expanduser("~/Documents/ideakeeper/gemini_profile"))
    profile_dir.mkdir(exist_ok=True, parents=True)

    desc_hint = f"Specific product details to isolate: {description}" if description else "the main clothing item"

    prompt = (
        f"This is a frame from a video. I need you to extract EXACTLY ONE item: {desc_hint}. "
        f"Please recreate this exact item precisely as it appears, but isolated on a pure white flat-lay background. "
        f"Keep every wrinkle, texture, and detail true to the image. Do not hallucinate or change the design. "
        f"Output ONLY the isolated product image."
    )
    
    print(f"[Gemini Web] Automating Chrome to extract product: {description}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = await browser.new_page()
            
            await page.goto("https://gemini.google.com/app")
            
            try:
                await page.wait_for_selector('div[contenteditable="true"]', timeout=3000)
            except:
                print("[Gemini Web] ⚠️ Not logged in. Please log in on the opened browser window...")
                await page.wait_for_selector('div[contenteditable="true"]', timeout=300000)
                
            print("[Gemini Web] Loaded Gemini conversation.")
            
            file_input = page.locator('input[type="file"]')
            await file_input.set_input_files(str(frame_path))
            
            await asyncio.sleep(3)
            
            chat_box = page.locator('div[contenteditable="true"]').first
            await chat_box.focus()
            await page.keyboard.type(prompt)
            
            await page.keyboard.press("Enter")
            print("[Gemini Web] Prompt submitted. Waiting 30s for image generation...")
            
            await asyncio.sleep(30)
            
            images = await page.locator('img').all()
            target_img_url = None
            for img in reversed(images):
                src = await img.get_attribute("src")
                if src and "googleusercontent.com" in src and "avatar" not in src:
                    target_img_url = src
                    break
            
            if target_img_url:
                print(f"[Gemini Web] Extracted image URL. Downloading...")
                b64 = await page.evaluate(f'''async () => {{
                    const resp = await fetch("{target_img_url}");
                    const blob = await resp.blob();
                    return new Promise((resolve, reject) => {{
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result);
                        reader.onerror = reject;
                        reader.readAsDataURL(blob);
                    }});
                }}''')
                
                header, encoded = b64.split(",", 1)
                dest_path.write_bytes(base64.b64decode(encoded))
                print(f"[Gemini Web] ✓ Saved product photo: {dest_path.name}")
                await browser.close()
                return dest_path
            else:
                print("[Gemini Web] ❌ Could not find generated image in UI.")
                await browser.close()
                return None
            
    except Exception as e:
        print(f"[Gemini Web] Error automating Chrome: {e}")
        return None

def generate_product_photo(frame_path: Path, dest_path: Path, description: str = "") -> Path | None:
    """Synchronous wrapper for internal async call (compatible with current main pipeline)"""
    return asyncio.run(generate_product_photo_async(frame_path, dest_path, description))


