"""
pipeline.py — polling endpoint backing the live pipeline-visualizer dashboard.

Mirrors app/services/pipeline_events.py so the frontend can render each
pipeline stage (intent check -> matching -> draft -> Alex's decision) as a
diagram instead of the uvicorn terminal, for demo purposes.
"""
from fastapi import APIRouter, Query
from app.services.pipeline_events import events_since

router = APIRouter()


@router.get("/pipeline/events")
async def pipeline_events(since: int = Query(0)):
    events = events_since(since)
    next_since = events[-1]["id"] if events else since
    return {"events": events, "since": next_since}
