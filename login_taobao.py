import os
from pathlib import Path
from playwright.sync_api import sync_playwright

def login_to_taobao():
    print("=========================================")
    print("Welcome to the Taobao Authenticator!")
    print("A browser will now open.")
    print("Please log in to your Taobao Account.")
    print("Once logged in and you see the Taobao homepage, you can close the browser window.")
    print("=========================================")
    
    profile_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "taobao_profile")))
    profile_dir.mkdir(exist_ok=True, parents=True)

    with sync_playwright() as p:
        # Launch persistent browser so cookies are saved
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 800}
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://login.taobao.com/")
        
        print("\n⏳ Browser opened! Please log in...")
        print("Waiting for you to close the browser...")
        
        try:
            # Wait until the user closes the page manually
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
            
        print("\n✅ Script complete. The login state is saved.")
        print("You can now safely use the pipeline to extract Taobao links.")

if __name__ == "__main__":
    login_to_taobao()
