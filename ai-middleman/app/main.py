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

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .database import init_db, get_db
from .services.matching_engine import MatchingEngine
from .routes.whatsapp_webhook import router as whatsapp_router
from .routes.friend import router as friend_router
from .routes.pipeline import router as pipeline_router
from .routes.dashboard_api import router as dashboard_api_router
from .routes.auth import router as auth_router
from .security import require_admin, security_settings, validate_production_configuration

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_configuration()

    await init_db()
    app.state.db_pool = await get_db()
    print("Database connected successfully!")
    yield

app = FastAPI(title="AI Middleman API", lifespan=lifespan)

_security = security_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_security.frontend_origins),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.middleware("http")
async def security_headers_and_request_limit(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > _security.max_request_bytes:
        return Response(status_code=413, content="Request too large")
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cache-Control", "no-store")
    if _security.secure_cookies:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

app.include_router(auth_router)
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

@app.post("/match", dependencies=[Depends(require_admin)])
async def test_match(request: Request):
    body = await request.json()
    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    if not isinstance(query, str) or len(query) > 4_000:
        raise HTTPException(status_code=422, detail="query must be text up to 4,000 characters")
    engine = MatchingEngine(app.state.db_pool)
    result = await engine.match(query)
    return result
