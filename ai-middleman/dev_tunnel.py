# dev_tunnel.py
# Opens a public tunnel to localhost:8000 for WhatsApp webhooks, bound to the
# RESERVED ngrok domain so it matches the Callback URL already configured in the
# Meta dashboard (otherwise ngrok mints a random URL and Meta can't reach us).
#
# Run this alongside uvicorn (port 8000). Keep it running while testing.
#
# Config (env, with sensible defaults):
#   NGROK_DOMAIN     reserved domain to bind (default: the project's reserved one)
#   NGROK_AUTHTOKEN  ngrok auth token (optional if already in your ngrok config)

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pyngrok import ngrok, conf

load_dotenv(Path(__file__).parent / ".env")

DOMAIN = os.getenv("NGROK_DOMAIN", "plating-marmalade-outthink.ngrok-free.dev")
PORT = int(os.getenv("PORT", "8000"))

if __name__ == "__main__":
    authtoken = os.getenv("NGROK_AUTHTOKEN")
    if authtoken:
        conf.get_default().auth_token = authtoken

    try:
        # domain= binds the reserved endpoint (ngrok v3 --domain). Without it,
        # ngrok would allocate a random *.ngrok-free.dev URL.
        tunnel = ngrok.connect(addr=PORT, proto="http", domain=DOMAIN)
    except Exception as e:
        print(f"\n[ERROR] Could not open tunnel on {DOMAIN}: {e}")
        print("Common causes: domain not reserved on this ngrok account, missing")
        print("authtoken, or another ngrok session already running (free tier = 1).")
        sys.exit(1)

    print(f"\n{'='*66}")
    print(f"Tunnel online: {tunnel.public_url}  ->  http://localhost:{PORT}")
    print(f"Meta Callback URL:  {tunnel.public_url}/webhook/whatsapp")
    print(f"{'='*66}")
    print("Verify from another shell:")
    print(f'  curl {tunnel.public_url}/health   # expect {{"status":"ok"}}')
    print("Press CTRL+C to stop the tunnel.\n")

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nClosing tunnel…")
        ngrok.disconnect(tunnel.public_url)
