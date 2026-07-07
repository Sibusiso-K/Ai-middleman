"""
conversation_manager.py — Manages multi-turn conversation threads.

One thread per friend (keyed by sender_number), holding an ordered log of
events (friend_message, draft_suggested, draft_sent, draft_edited,
draft_skipped) in thread_events. This replaces the old single-row
"conversation_state" model that overwrote its one pending draft on every
new request — the dashboard needs full thread history to show ongoing
conversation and to resolve references like "connect me with the second
one" against the most recent draft_suggested event.
"""

import json
from typing import Optional, Dict, Any, List
import asyncpg


class ConversationManager:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def get_or_create_thread(self, sender_number: str) -> Dict[str, Any]:
        """Fetch the thread for a sender, creating it if it doesn't exist yet."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, sender_number, autonomy_mode FROM threads WHERE sender_number = $1",
                sender_number
            )
            if row:
                return dict(row)
            row = await conn.fetchrow("""
                INSERT INTO threads (sender_number)
                VALUES ($1)
                RETURNING id, sender_number, autonomy_mode
            """, sender_number)
            return dict(row)

    async def add_event(self, thread_id: int, event_type: str, payload: dict) -> int:
        """Append an event to a thread's log. Returns the new event id."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO thread_events (thread_id, event_type, payload)
                VALUES ($1, $2, $3::jsonb)
                RETURNING id
            """, thread_id, event_type, json.dumps(payload))
            await conn.execute(
                "UPDATE threads SET updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                thread_id
            )
        return row['id']

    async def tag_event_language(self, event_id: int, language: str) -> None:
        """Record the detected language on a friend_message event, after the
        fact — classification happens in a background task, after the event
        was already inserted. This is what get_recent_message_language reads
        back to keep language "sticky" across a conversation instead of
        re-guessing from scratch on every short, ambiguous message."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE thread_events SET payload = payload || jsonb_build_object('language', $2::text) WHERE id = $1",
                event_id, language,
            )

    async def get_recent_message_language(self, thread_id: int, before_event_id: int) -> Optional[str]:
        """Return the most recently tagged language on an earlier friend_message
        in this thread (the conversation's established language), or None if
        none is tagged yet — used so a short, ambiguous follow-up ("anyone
        else") inherits the language the conversation has actually been in,
        rather than the classifier re-guessing on a message with almost no
        signal."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT payload->>'language' AS language FROM thread_events
                WHERE thread_id = $1 AND event_type = 'friend_message'
                  AND id < $2 AND payload ? 'language'
                ORDER BY created_at DESC LIMIT 1
                """,
                thread_id, before_event_id,
            )
        return rows[0]["language"] if rows else None

    async def get_recent_events(self, thread_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent events for a thread, oldest first."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, event_type, payload, created_at
                FROM thread_events
                WHERE thread_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, thread_id, limit)
        events = [dict(r) for r in reversed(rows)]
        for e in events:
            e['payload'] = json.loads(e['payload']) if isinstance(e['payload'], str) else e['payload']
        return events

    async def get_last_open_alex_question(self, thread_id: int) -> Optional[str]:
        """
        Return the text of Alex's most recent free-text reply if it reads like
        a clarifying question (ends in '?') and nothing has happened on the
        thread since — used to resolve a short confirmation from the friend
        ("yeah") into the request Alex was actually asking about.
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT event_type, payload FROM thread_events
                WHERE thread_id = $1
                ORDER BY created_at DESC
                OFFSET 1 LIMIT 1
            """, thread_id)
        if not row or row['event_type'] != 'alex_reply':
            return None
        payload = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
        text = (payload.get('text') or '').strip()
        return text if text.endswith('?') else None

    async def get_last_sent_match(self, thread_id: int) -> Optional[dict]:
        """
        Return the single match that was actually delivered to the friend in
        the most recent resolved draft_suggested event — used to answer
        follow-ups like "send me her details" without re-running the matcher.
        Falls back to the top-confidence match if the delivered text doesn't
        clearly identify which one was used (e.g. it was edited).
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT payload FROM thread_events
                WHERE thread_id = $1 AND event_type = 'draft_suggested'
                ORDER BY created_at DESC LIMIT 1
            """, thread_id)
        if not row:
            return None
        payload = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
        matches = payload.get('matches') or []
        if not matches:
            return None
        sent_text = payload.get('draft_reply', '') or ''
        for m in matches:
            name = m.get('name', '')
            if name and name in sent_text:
                return m
        return matches[0]  # highest-confidence match as fallback

    async def get_last_matches(self, thread_id: int) -> Optional[List[dict]]:
        """
        Return the match list from the most recent draft_suggested event,
        used to resolve follow-ups like "connect me with the second one"
        without re-running the matching engine.
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT payload FROM thread_events
                WHERE thread_id = $1 AND event_type = 'draft_suggested'
                ORDER BY created_at DESC
                LIMIT 1
            """, thread_id)
        if not row:
            return None
        payload = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
        return payload.get('matches')

    async def get_last_draft_payload(self, thread_id: int) -> Optional[dict]:
        """Return the full payload of the most recent draft_suggested event.
        Used to check draft_type (e.g. 'named_contact_confirmation') for
        context-sensitive follow-up handling."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT payload FROM thread_events
                WHERE thread_id = $1 AND event_type = 'draft_suggested'
                ORDER BY created_at DESC
                LIMIT 1
            """, thread_id)
        if not row:
            return None
        return json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']

    async def get_latest_pending_draft(self, thread_id: int) -> Optional[Dict[str, Any]]:
        """
        Return the most recent draft_suggested event for a thread if it is
        still awaiting action (i.e. no later draft_sent/edited/skipped event
        exists for it).
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, payload, created_at
                FROM thread_events
                WHERE thread_id = $1 AND event_type = 'draft_suggested'
                ORDER BY created_at DESC
                LIMIT 1
            """, thread_id)
            if not row:
                return None
            resolved = await conn.fetchval("""
                SELECT COUNT(*) FROM thread_events
                WHERE thread_id = $1
                  AND event_type IN ('draft_sent', 'draft_edited', 'draft_skipped')
                  AND created_at > $2
            """, thread_id, row['created_at'])
        if resolved:
            return None
        payload = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
        payload['event_id'] = row['id']
        return payload

    async def mark_draft_handled(self, thread_id: int, action: str, final_text: str = "") -> None:
        """
        Log the resolution of the thread's latest pending draft.
        action: 'sent', 'edited', or 'skipped'.
        """
        event_type = {"sent": "draft_sent", "edited": "draft_edited", "skipped": "draft_skipped"}[action]
        await self.add_event(thread_id, event_type, {"final_text": final_text})

    async def get_latest_pending_update(self, thread_id: int) -> Optional[Dict[str, Any]]:
        """Return the most recent update_pending event if not yet resolved
        (i.e. no later contact_updated or update_ignored event exists)."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, payload, created_at
                FROM thread_events
                WHERE thread_id = $1 AND event_type = 'update_pending'
                ORDER BY created_at DESC
                LIMIT 1
            """, thread_id)
            if not row:
                return None
            resolved = await conn.fetchval("""
                SELECT COUNT(*) FROM thread_events
                WHERE thread_id = $1
                  AND event_type IN ('contact_updated', 'update_ignored')
                  AND created_at > $2
            """, thread_id, row['created_at'])
        if resolved:
            return None
        payload = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
        payload['event_id'] = row['id']
        return payload

    async def set_autonomy_mode(self, thread_id: int, mode: str) -> None:
        """Set a thread's autonomy mode ('manual' or 'autonomous')."""
        if mode not in ("manual", "autonomous"):
            raise ValueError(f"Invalid autonomy mode: {mode}")
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE threads SET autonomy_mode = $2, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                thread_id, mode
            )

    async def list_threads(self) -> List[Dict[str, Any]]:
        """List all threads with their latest activity, most recent first."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT t.id, t.sender_number, t.autonomy_mode, t.updated_at,
                       (SELECT COUNT(*) FROM thread_events e
                        WHERE e.thread_id = t.id AND e.event_type = 'draft_suggested'
                          AND NOT EXISTS (
                              SELECT 1 FROM thread_events e2
                              WHERE e2.thread_id = t.id
                                AND e2.event_type IN ('draft_sent', 'draft_edited', 'draft_skipped')
                                AND e2.created_at > e.created_at
                          )) AS pending_count
                FROM threads t
                ORDER BY t.updated_at DESC
            """)
        return [dict(r) for r in rows]

    async def get_pending_count(self) -> int:
        """Count how many threads currently have an unresolved draft."""
        threads = await self.list_threads()
        return sum(1 for t in threads if t['pending_count'] > 0)
