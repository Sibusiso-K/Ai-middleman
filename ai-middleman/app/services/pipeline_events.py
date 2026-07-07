"""
pipeline_events.py — in-memory feed of pipeline stage events for the demo
visualizer dashboard.

The uvicorn terminal already shows every step via slog(); this just mirrors
the key steps into a small ring buffer that the frontend can poll, so a
non-technical audience can watch the pipeline run as a diagram instead of
reading log lines. Single-process, in-memory by design — this is a demo aid,
not an audit log.
"""
from collections import deque
from itertools import count
import time

_events = deque(maxlen=200)
_next_id = count(1)

# Stage keys the frontend diagram knows how to light up. Anything else is
# still recorded (and shown in the feed) but won't highlight a node.
STAGES = (
    "received", "relaying", "checking", "intent",
    "updating", "named_lookup",
    "matching", "drafting", "awaiting_approval", "resolved",
)


def emit(stage: str, message: str, **meta) -> None:
    _events.append({
        "id": next(_next_id),
        "ts": time.time(),
        "stage": stage,
        "message": message,
        "meta": meta,
    })


def events_since(last_id: int) -> list[dict]:
    return [e for e in _events if e["id"] > last_id]
