-- Thread-based conversation state for the dashboard redesign.
--
-- Replaces the single-row-per-sender "conversation_state" model (one
-- pending draft, overwritten on every new request) with a persistent
-- multi-turn thread per friend, so the dashboard can show ongoing
-- conversations and resolve references like "connect me with the
-- second one" against prior turns instead of only the latest one.
--
-- conversation_state, match_history, and introduction_requests are left
-- in place (still created by earlier migrations) but are no longer
-- written to by the application — threads/thread_events supersede them.

CREATE TABLE IF NOT EXISTS threads (
    id SERIAL PRIMARY KEY,
    sender_number VARCHAR(20) UNIQUE NOT NULL,
    autonomy_mode VARCHAR(20) NOT NULL DEFAULT 'manual', -- 'manual' or 'autonomous'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- One row per turn/action in a thread: an incoming friend message, a
-- generated draft suggestion, or the resolution of that draft (sent,
-- edited, or skipped). Ordered by created_at within a thread.
CREATE TABLE IF NOT EXISTS thread_events (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES threads(id),
    event_type VARCHAR(20) NOT NULL, -- 'friend_message', 'draft_suggested', 'draft_sent', 'draft_edited', 'draft_skipped'
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_threads_sender ON threads(sender_number);
CREATE INDEX IF NOT EXISTS idx_thread_events_thread ON thread_events(thread_id, created_at);
