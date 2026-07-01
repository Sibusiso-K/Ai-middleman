"""
main.py — FastAPI application entrypoint for the AI Middleman API.

Initialises the database connection pool on startup, registers the WhatsApp
webhook router, and exposes health-check and test-match endpoints. Serves as
the central orchestration point that wires together all services.

Exposed endpoints:
  GET  /              — API status message
  GET  /health        — Health check (returns {"status": "ok"})
  POST /match         — Test endpoint for the matching pipeline
  GET  /webhook/whatsapp  — Meta webhook verification (via whatsapp_webhook router)
  POST /webhook/whatsapp  — Incoming WhatsApp message handler (via whatsapp_webhook router)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env BEFORE any other imports that might need env vars
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from .database import init_db, get_db
from .services.matching_engine import MatchingEngine
from .routes.whatsapp_webhook import router as whatsapp_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup token check
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "NOT_FOUND")
    print(f"[STARTUP] WHATSAPP_ACCESS_TOKEN length: {len(token)}")
    print(f"[STARTUP] Token start: {token[:30]}")
    print(f"[STARTUP] Token end: {token[-10:]}")
    
    await init_db()
    app.state.db_pool = await get_db()
    print("Database connected successfully!")
    yield

app = FastAPI(title="AI Middleman API", lifespan=lifespan)

app.include_router(whatsapp_router)

@app.get("/")
async def root():
    return {"message": "AI Middleman API is running"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/match")
async def test_match(request: Request):
    body = await request.json()
    query = body.get("query", "")
    if not query:
        return {"error": "query is required"}
    engine = MatchingEngine(app.state.db_pool)
    result = await engine.match(query)
    return result
