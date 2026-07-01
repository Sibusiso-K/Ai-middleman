# dev_tunnel.py
# Creates a public URL tunnel to localhost:8000 for testing WhatsApp webhooks locally
# Run this BEFORE starting uvicorn, then use the printed URL as your Meta webhook Callback URL

from pyngrok import ngrok

if __name__ == "__main__":
    public_url = ngrok.connect(8000)
    print(f"\n{'='*60}")
    print(f"Public webhook URL: {public_url}")
    print(f"Use this in Meta dashboard as Callback URL:")
    print(f"{public_url}/webhook/whatsapp")
    print(f"{'='*60}\n")
    print("Press CTRL+C to stop the tunnel")

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nTunnel closed")
        ngrok.disconnect(public_url)