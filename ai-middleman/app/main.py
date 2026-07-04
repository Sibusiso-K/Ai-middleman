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
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .database import init_db, get_db
from .services.matching_engine import MatchingEngine
from .routes.whatsapp_webhook import router as whatsapp_router
from .routes.friend import router as friend_router
from .routes.pipeline import router as pipeline_router
from .routes.dashboard_api import router as dashboard_api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup token check — log only the length, never any fragment of the token.
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "NOT_FOUND")
    print(f"[STARTUP] WHATSAPP_ACCESS_TOKEN length: {len(token)}")

    await init_db()
    app.state.db_pool = await get_db()
    print("Database connected successfully!")
    yield

app = FastAPI(title="AI Middleman API", lifespan=lifespan)

# Allow the Vercel-hosted friend chat frontend (or any browser) to call
# /friend/* cross-origin. Demo-scoped: wide open by default, restrict via
# CORS_ALLOWED_ORIGINS (comma-separated) if this ever needs to be tighter.
_cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _cors_origins == "*" else _cors_origins.split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(whatsapp_router)
app.include_router(friend_router)
app.include_router(pipeline_router)
app.include_router(dashboard_api_router)

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
