import asyncio

async def background_task(url, vid):
    print(f"[{vid}] Background task started: {url}")
    await asyncio.sleep(2)
    print(f"[{vid}] Background task finished.")

async def webhook_handler():
    print("Webhook received.")
    asyncio.create_task(background_task("http://example.com", "v123"))
    print("Webhook returning.")

async def main():
    await webhook_handler()
    # Need to keep event loop alive for background task
    await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
