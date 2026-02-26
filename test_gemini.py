import requests
import json
import os

API_KEY = "AIzaSyCS2vrrkL0kcUKfi4c6h62eJq079cd1qwE"
url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={API_KEY}"

payload = {
    "instances": [
        {"prompt": "A clean e-commerce product photo of a white t-shirt on a white background"}
    ],
    "parameters": {
        "sampleCount": 1,
    }
}

headers = {'Content-Type': 'application/json'}
response = requests.post(url, headers=headers, json=payload)
print(response.status_code)
if response.status_code == 200:
    print("API Key is valid and Imagen generation works!")
else:
    print(response.text)
