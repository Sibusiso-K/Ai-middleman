"""Test Featherless API connectivity."""
import asyncio, httpx, os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

api_key = os.getenv('FEATHERLESS_API_KEY') or os.getenv('OPENROUTER_API_KEY')
api_url = os.getenv('FEATHERLESS_API_URL', 'https://api.featherless.ai/v1/chat/completions')
model = os.getenv('FEATHERLESS_MODEL', 'NousResearch/Meta-Llama-3.1-8B-Instruct')

print(f'API URL: {api_url}', flush=True)
print(f'Model: {model}', flush=True)
print(f'API Key present: {bool(api_key)}', flush=True)
print(f'API Key length: {len(api_key) if api_key else 0}', flush=True)
print(f'API Key start: {api_key[:20] if api_key else "NONE"}...', flush=True)
print(flush=True)

async def test():
    async with httpx.AsyncClient() as client:
        try:
            print("Sending request...", flush=True)
            response = await client.post(
                api_url,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': 'Reply with only YES or NO. Is the sky blue?'}],
                    'temperature': 0.1,
                    'max_tokens': 5
                },
                timeout=15.0
            )
            print(f'Status: {response.status_code}', flush=True)
            print(f'Body: {response.text[:500]}', flush=True)
        except Exception as e:
            print(f'Exception type: {type(e).__name__}', flush=True)
            print(f'Exception: {e!r}', flush=True)
            print(f'Exception str: {str(e)}', flush=True)

asyncio.run(test())
print("Done.", flush=True)