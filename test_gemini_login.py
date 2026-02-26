import os
from pathlib import Path
from playwright.sync_api import sync_playwright

def login_to_gemini():
    print("=========================================")
    print("Welcome to the Gemini Web Authenticator!")
    print("A Chrome browser will now open.")
    print("Please log in to your Google Account.")
    print("Once logged in and you see the Gemini chat interface, close the browser.")
    print("=========================================")
    
    profile_dir = Path(os.path.expanduser("~/Documents/ideakeeper/gemini_profile"))
    profile_dir.mkdir(exist_ok=True, parents=True)

    with sync_playwright() as p:
        # Launch persistent browser so cookies are saved
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,  # You must see the browser to log in
            channel="chrome", # Use normal Chrome to avoid basic bot checks
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()
        page.goto("https://gemini.google.com/app")
        
        print("\n⏳ Browser opened! Please log in...")
        print("Waiting for the chat box to appear...")
        
        try:
            # Wait up to 10 minutes for the user to finish logging in
            page.wait_for_selector('div[contenteditable="true"]', timeout=600000)
            print("\n✅ Success! You've logged into Gemini Web.")
            print("You can now safely close the Chrome window and use the pipeline.")
        except Exception as e:
            print("\n❌ Timed out waiting for login. If you closed the browser early, that's fine.")
            
        print("Script complete. The pipeline is now ready to use!")
        # Let it stay open a little longer if they just logged in
        page.wait_for_timeout(5000)
        browser.close()

if __name__ == "__main__":
    login_to_gemini()
