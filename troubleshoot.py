import os
import requests
from dotenv import load_dotenv

load_dotenv()

print(os.getenv("OPENAI_API_KEY"))
api_key = os.getenv("LLM_API_KEY")
base_url = os.getenv("LLM_BASE_URL")
model = os.getenv("LLM_MODEL")


print(f"Key loaded:  {'YES' if api_key else 'NO'}")
print(f"Key prefix:  {api_key[:10]}..." if api_key else "Key prefix:  (none)")
print(f"Base URL:    {base_url}")
print(f"Model:       {model}")
print()

# Direct REST call — bypasses the openai library to isolate the issue
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
payload = {"contents": [{"parts": [{"text": "Say hello"}]}]}

resp = requests.post(url, json=payload, timeout=15)
print(f"HTTP status: {resp.status_code}")
print(f"Response:    {resp.text[:600]}")
