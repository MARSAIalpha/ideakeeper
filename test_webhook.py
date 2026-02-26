import requests
import time

def test_pipeline():
    print("Testing the Asset Library Webhook...")
    
    url = "http://localhost:8000/webhook/openclaw"
    payload = {
        "url": "https://www.xiaohongshu.com/discovery/item/6437e6c60000000013033c1e?source=webshare&xhsshare=pc_web&xsec_token=ABD56ETtHF6l3VF0cE1nUJbk1wcsykUw7AdUqFgFqErMM=&xsec_source=pc_share"
    }
    
    try:
        response = requests.post(url, json=payload)
        print("Webhook response:", response.status_code, response.json())
    except Exception as e:
        print("Failed to call webhook:", e)

if __name__ == "__main__":
    test_pipeline()
    print("Test triggered. Check the FastAPI server logs for the background process output.")
