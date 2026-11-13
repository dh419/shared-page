import os
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

test_models = ['gemini-2.5-flash-lite', 'gemini-3.1-flash-lite', 'gemini-3.5-flash-lite', 'gemini-3.8-flash']

for m in test_models:
    try:
        res = client.models.generate_content(model=m, contents="ping")
        print(f"SUCCESS: {m}")
        break
    except Exception as e:
        print(f"FAIL: {m} -> {e}")
