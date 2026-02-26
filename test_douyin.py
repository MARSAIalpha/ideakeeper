import asyncio
from playwright.async_api import async_playwright

async def main():
    extracted_urls = set()
    url = "https://v.douyin.com/iU7tVCM62o4/"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()
        
        async def on_response(response):
            low_url = response.url.lower()
            if response.request.resource_type == "media" or ".mp4" in low_url:
                print(f"[MEDIA] {response.url}")
                extracted_urls.add(response.url)
            elif "aweme" in low_url and response.request.resource_type in ["xhr", "fetch"]:
                try:
                    text = await response.text()
                    import json
                    data = json.loads(text)
                    def find_urls(d):
                        if isinstance(d, dict):
                            for k, v in d.items():
                                if k in ["url_list", "play_addr"] and isinstance(v, (list, dict)):
                                    print(f"[JSON] Found {k}: {v}")
                                find_urls(v)
                        elif isinstance(d, list):
                            for item in d:
                                find_urls(item)
                    find_urls(data)
                except Exception:
                    pass
                
        page.on("response", on_response)
        
        print("Navigating...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        # Check standard video tags
        dom_video = await page.evaluate("() => { const v = document.querySelector('video'); return v ? v.src : null; }")
        print(f"[DOM] Video querySelector: {dom_video}")
        
        # Checking window._ROUTER_DATA
        router_data_str = await page.evaluate("() => { return window._ROUTER_DATA ? JSON.stringify(window._ROUTER_DATA).slice(0, 500) + '...' : 'none'; }")
        print(f"[DOM] window._ROUTER_DATA : {router_data_str}")
        
        router_video_urls = await page.evaluate("""
        () => {
            if (!window._ROUTER_DATA) return null;
            let urls = [];
            let str = JSON.stringify(window._ROUTER_DATA);
            // simple regex to find play_addr or normal mp4 links
            let matches = str.match(/https:\\/\\/[^"']+(?:mp4|video|v[0-9]+[^"']+douyinvod)[^"']+/g);
            return matches;
        }
        """)
        print(f"[DOM] router_video_urls: {router_video_urls}")

        try:
            await page.mouse.click(200, 300)
            print("Clicked screen")
        except Exception:
            pass
            
        await asyncio.sleep(5)
        
        await browser.close()
        
    print(f"Extracted URLs: {extracted_urls}")

asyncio.run(main())
