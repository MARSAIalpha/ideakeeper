import asyncio
from services.ingestion import IngestionRequest
from main import background_video_processing

async def run_test():
    print("Forcing full synchronous pipeline...")
    req = IngestionRequest(url="https://v.douyin.com/iU7tVCM62o4/")
    await background_video_processing(req, "test_wanx_gen")
    print("Done")

if __name__ == "__main__":
    asyncio.run(run_test())
