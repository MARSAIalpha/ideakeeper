import asyncio
from playwright.async_api import async_playwright

async def main():
    url = "https://www.xiaohongshu.com/explore/685e78b5000000001c030b19?note_flow_source=wechat&xsec_token=CBQe3cRW2015atwFltdOrtUNACjXV7alWQIc5QnCx52Xk="
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        # Wait for video element
        try:
            await page.wait_for_selector("video", timeout=10000)
            video_src = await page.evaluate('document.querySelector("video").src')
            print(f"Video URL: {video_src}")
        except Exception as e:
            print("Failed to find video element")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
