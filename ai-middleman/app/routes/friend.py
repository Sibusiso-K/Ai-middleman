"""
friend.py — "Sam" (the friend) side of the AI Middleman loop.

The friend dashboard posts here to role-play Sam. Each send:
  1. records a friend_message event on the single Sam<->Alex thread,
  2. relays the text to Alex's real WhatsApp (send FROM our Cloud API number
     650746242 TO Alex 736013348) so it shows up in his 650746242 chat,
  3a. if it looks like a follow-up asking for the last-matched contact's
      details (phone/email), looks that contact up and pushes Alex a
      Send/Skip-gated draft with the actual details — revealing PII still
      requires his approval, it just doesn't need a fresh matching pass;
  3b. if it's a short confirmation ("yeah") right after Alex asked a
      clarifying question ("Oh you mean AI consulting?"), runs matching on
      Alex's clarified phrasing instead of Sam's one-word reply;
  3c. otherwise runs the intent/matching/draft pipeline (typo-tolerant), and
      if it's a contact request, pushes Alex a clearly-marked draft with
      Send/Skip interactive buttons and records a draft_suggested event.

The dashboard then polls GET /friend/thread to render the conversation and any
replies Alex sends back (which arrive via the webhook as alex_reply / draft_*).
"""

import asyncio
import os
import re
from fastapi import APIRouter, Request, BackgroundTasks, UploadFile, File
from dotenv import load_dotenv
from pathlib import Path

from app.services.intent_classifier import IntentClassifier, IntentClassificationError
from app.services.matching_engine import MatchingEngine
from app.services.draft_generator import DraftGenerator
from app.services.conversation_manager import ConversationManager
from app.services.whatsapp_client import WhatsAppClient
from app.services.pipeline_events import emit
from app.log_safe import slog

load_dotenv(Path(__file__).parent.parent.parent / ".env")

router = APIRouter()

ALEX_NUMBER = os.getenv("ALEX_WHATSAPP_NUMBER", "27736013348")
FRIEND_NAME = os.getenv("FRIEND_SIM_NAME", "Sam")
EDIT_FLOW_ID = os.getenv("WHATSAPP_EDIT_FLOW_ID")

# Fast, LLM-free detector for "send me their details" follow-ups — no need to
# wait on an intent-classifier round trip for a pattern this unambiguous.
_DETAILS_REQUEST_RE = re.compile(
    r"\b(send|share|give|forward)\b.{0,25}\b(detail|contact|number|phone|email|info)"
    r"|\b(their|his|her)\s+(detail|contact|number|phone|email)",
    re.IGNORECASE,
)


def _looks_like_details_request(text: str) -> bool:
    return bool(_DETAILS_REQUEST_RE.search(text))


# Short, whole-message confirmations — used to detect "yeah"/"yep"/"correct"
# replying to Alex's own clarifying question ("Oh you mean AI consulting?").
_AFFIRMATION_RE = re.compile(
    r"^\s*(yeah|yea|yeh|yes|yep|yup|sure|ok|okay|correct|right|exactly|"
    r"that'?s (it|right|correct))[.!]*\s*$",
    re.IGNORECASE,
)


def _looks_like_affirmation(text: str) -> bool:
    return bool(_AFFIRMATION_RE.match(text))


# --- Follow-up selection: "connect me with John", "Sally works, send details",
# "the second one", "both of them" -----------------------------------------
# Sam picks from the 1-3 people the last draft suggested. We resolve WHO by
# name or position, gated by a positive cue (so "John's too junior, anyone
# else?" is NOT read as "connect me with John").
_ORDINALS = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2}

_POSITIVE_CUE_RE = re.compile(
    r"\b(connect|intro|introduce|link me|hook me|details?|contact|number|phone|"
    r"email|send|share|forward|perfect|great|works?|ideal|sounds good|go with|"
    r"let'?s go|yes|yeah|yep|sure|please)\b",
    re.IGNORECASE,
)
# Signals a rejection or a request for different people, not a pick.
_NEGATIVE_CUE_RE = re.compile(
    r"\b(anyone else|someone else|somebody else|instead|too junior|too senior|"
    r"rather not|don'?t|do not|not (him|her|them|really|keen|sure)|no thanks)\b",
    re.IGNORECASE,
)


def _join_names(names: list) -> str:
    """['John'] -> 'John'; ['John','Sally'] -> 'John and Sally';
    ['A','B','C'] -> 'A, B and C'."""
    if not names:
        return "them"
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _resolve_selected_contacts(text: str, matches: list) -> list:
    """Given Sam's follow-up and the 1-3 previously-suggested matches, return
    the subset Sam is picking — by name ("connect me with John and Sally"), by
    position ("the second one"), or all ("both of them"). Returns [] if the
    message doesn't clearly point at a suggested contact, or reads as a
    rejection rather than a pick."""
    if not matches:
        return []
    if _NEGATIVE_CUE_RE.search(text):
        return []

    low = f" {text.lower()} "

    # Self-sufficient group selections — "both of them", "all three", "all of
    # them", "them all", "everyone" can only mean "all the people you
    # suggested", so they don't need a separate connect/send verb.
    if re.search(r"\b(both|all of (them|those)|all three|them all|everyone)\b", low):
        return list(matches)

    # Everything below (a bare pronoun, a position, or a name) can also appear
    # in a question ("what about the second one?", "are they any good?"), so it
    # only counts as a pick when there's a positive cue and no rejection.
    if not _POSITIVE_CUE_RE.search(text):
        return []

    # "connect me with them / dem / those" -> everyone suggested. Safe here
    # because the positive cue above rules out the bare-question case.
    if re.search(r"\b(them|dem|those|these)\b", low):
        return list(matches)

    selected, seen = [], set()

    def _add(idx: int):
        if 0 <= idx < len(matches) and idx not in seen:
            selected.append(matches[idx])
            seen.add(idx)

    for word, idx in _ORDINALS.items():
        if re.search(rf"\b{re.escape(word)}\b", low):
            _add(idx)

    for i, m in enumerate(matches):
        name = (m.get("name") or "").strip()
        if not name:
            continue
        first = name.split()[0].lower()
        # Allow an optional possessive ("John's" / "Johns details").
        if len(first) >= 3 and re.search(rf"\b{re.escape(first)}(?:['’]?s)?\b", low):
            _add(i)

    return selected


def _format_history_for_draft(events: list) -> tuple[str, bool]:
    """Turn recent thread_events into a compact "Sam: ... / Alex: ..." transcript
    for the draft prompt, skipping pending/system events. Returns (history_text,
    is_first_message) — is_first_message is True only if no prior turn exists,
    so the draft prompt knows whether an opening greeting is appropriate."""
    lines = []
    for e in events:
        p = e.get("payload", {})
        if e["event_type"] == "friend_message":
            lines.append(f"{FRIEND_NAME}: {p.get('text', '')}")
        elif e["event_type"] == "draft_sent":
            lines.append(f"Alex: {p.get('final_text', '')}")
        elif e["event_type"] == "alex_reply":
            lines.append(f"Alex: {p.get('text', '')}")
    # The current message being drafted for is the last friend_message in the
    # log (already recorded before this runs) — exclude it from "history".
    if lines and lines[-1].startswith(f"{FRIEND_NAME}:"):
        lines = lines[:-1]
    is_first_message = len(lines) == 0
    return "\n".join(lines[-8:]), is_first_message


async def _handle_followup_selection(db_pool, thread_id: int, text: str, whatsapp: "WhatsAppClient") -> bool:
    """
    Handle a follow-up where Sam picks from the people the last draft
    suggested — "connect me with John", "Sally works, send her details",
    "the second one", "both of them" — by looking up the chosen contact(s)
    and pushing Alex a Send/Skip-gated draft with the actual phone/email.
    Revealing PII still requires Alex's approval; this just skips a fresh
    matching pass. Returns True if handled (caller should not also run the
    full matching pipeline).
    """
    manager = ConversationManager(db_pool)
    matches = await manager.get_last_matches(thread_id)
    if not matches:
        return False  # no recent suggestions — this can't be a pick

    selected = _resolve_selected_contacts(text, matches)

    # Generic "send me their details" with no name/position: if only one
    # person was suggested (or one was actually sent), that's who they mean.
    if not selected and _looks_like_details_request(text):
        last = await manager.get_last_sent_match(thread_id)
        if last:
            selected = [last]

    if not selected:
        return False  # not a pick — fall through to the normal pipeline

    emit("checking", "🔍 Sam is picking from the people we suggested")

    # Look up real contact details for each selected person.
    picked = []
    async with db_pool.acquire() as conn:
        for m in selected:
            cid = m.get("contact_id")
            if not cid:
                continue
            c = await conn.fetchrow(
                "SELECT full_name, phone, email FROM contacts WHERE id = $1", cid
            )
            if not c or not (c["phone"] or c["email"]):
                continue
            details = " / ".join(filter(None, [
                f"📞 {c['phone']}" if c["phone"] else None,
                f"📧 {c['email']}" if c["email"] else None,
            ]))
            first = c["full_name"].split()[0] if c["full_name"] else "them"
            picked.append({"match": m, "full_name": c["full_name"], "first": first, "details": details})

    if not picked:
        return False  # couldn't resolve any real details — let the pipeline try

    if len(picked) == 1:
        p = picked[0]
        draft = f"Here's {p['first']} for you — {p['details']}. Tell {p['first']} I sent you 🤝"
    else:
        body = "\n".join(f"{p['first']} — {p['details']}" for p in picked)
        names = _join_names([p["first"] for p in picked])
        draft = f"Here you go 🤝\n{body}\nTell {names} I sent you!"

    event_id = await manager.add_event(thread_id, "draft_suggested", {
        "original_message": text,
        "draft_reply": draft,
        "matches": [p["match"] for p in picked],
    })
    buttons = [
        {"type": "reply", "reply": {"id": f"send_{event_id}", "title": "✅ Send"}},
        {"type": "reply", "reply": {"id": f"skip_{event_id}", "title": "❌ Skip"}},
    ]
    who = _join_names([p["full_name"] for p in picked])
    draft_body = (
        f"🤖 *{FRIEND_NAME} is asking for {who}'s contact details*\n\n"
        f"*Draft:*\n{draft}\n\n"
        f"Tap Send to share it, or Skip to hold off."
    )
    await whatsapp.send_interactive_buttons(to=ALEX_NUMBER, body_text=draft_body, buttons=buttons)
    emit("awaiting_approval", f"📤 Draft with {who}'s details sent to Alex — waiting for Send/Skip")
    return True


async def _run_matching_and_push_draft(
    db_pool, thread_id: int, whatsapp: "WhatsAppClient",
    request_text: str, display_text: str, uncertain: bool = False,
    candidates: list | None = None,
    search_query: str | None = None,
    language: str = "English",
):
    """Run the matching+draft pipeline for request_text and push a Send/Skip
    draft to Alex. display_text is what's shown as "{FRIEND_NAME} asked" (may
    differ from request_text when resolved from a confirmed clarification).
    candidates, if provided, skips Stage 1's DB query (already fetched
    concurrently with intent classification by the caller).

    search_query is what Stage 1/2 actually search and reason against — the
    English rendering of the message when the sender wrote in one of South
    Africa's other official languages, since Stage 1 is a plain keyword match
    against English contact data. request_text (Sam's own words) is always
    what gets stored/shown and what the draft is generated in reply to, so
    Alex sees the real conversation, not a translation. language drives which
    language DraftGenerator replies in."""
    manager = ConversationManager(db_pool)
    engine = MatchingEngine(db_pool)
    search_query = search_query or request_text
    emit("matching", f"🔗 Searching contacts for: \"{search_query}\"")
    result = await engine.match(search_query, candidates=candidates)
    all_matches = result.get("matches", [])
    viable = [m for m in all_matches if m.get("confidence", 0) >= 0.5]
    emit("matching", f"🔗 Found {len(viable)} good match(es)" if viable else "🔗 No confident match found")

    # The matching LLM call already wrote the draft in the same round-trip
    # (see agent.py's draft_reply field) — only fall back to a second,
    # separate LLM call if it came back empty for some reason.
    draft = result.get("draft_reply") or ""
    if draft:
        emit("drafting", "✍️ Draft written in the same pass as matching")
    else:
        generator = DraftGenerator()
        emit("drafting", "✍️ Writing a suggested reply")
        recent_events = await manager.get_recent_events(thread_id, limit=20)
        history, is_first_message = _format_history_for_draft(recent_events)
        draft = await generator.generate_draft(
            original_request=request_text,
            matches=viable,
            conversation_history=history,
            is_first_message=is_first_message,
            language=language,
        )

    event_id = await manager.add_event(thread_id, "draft_suggested", {
        "original_message": request_text,
        "draft_reply": draft,
        "matches": all_matches,
    })

    # WhatsApp interactive messages can't mix reply buttons with a Flow
    # button in one message, so Send/Skip stay as reply buttons here and
    # Edit (if configured) goes out as a separate Flow message below.
    buttons = [
        {"type": "reply", "reply": {"id": f"send_{event_id}", "title": "✅ Send"}},
        {"type": "reply", "reply": {"id": f"skip_{event_id}", "title": "❌ Skip"}},
    ]
    uncertain_note = (
        "⚠️ _(couldn't auto-verify this was a request — sending a draft anyway)_\n\n"
        if uncertain else ""
    )
    edit_hint = (
        "Tap Send to use it as-is, or use the Edit form below to tweak it."
        if EDIT_FLOW_ID else
        "Tap Send to use it as-is, or reply EDIT <your version> to tweak it."
    )
    draft_body = (
        f"🤖 *Suggested reply to {FRIEND_NAME}*\n\n"
        f"{uncertain_note}"
        f"_{FRIEND_NAME} asked:_ {display_text}\n\n"
        f"*Draft:* {draft}\n\n"
        f"{edit_hint}"
    )
    await whatsapp.send_interactive_buttons(to=ALEX_NUMBER, body_text=draft_body, buttons=buttons)

    if EDIT_FLOW_ID:
        await whatsapp.send_flow(
            to=ALEX_NUMBER,
            flow_id=EDIT_FLOW_ID,
            screen="EDIT_DRAFT",
            cta="Edit draft",
            body_text="Want to tweak the wording before it goes out? Edit it here.",
            initial_data={"draft_text": draft},
        )

    emit("awaiting_approval", "📤 Sent to Alex for approval — waiting for Send/Skip")


async def _process_sam_message(db_pool, thread_id: int, text: str, friend_event_id: int):
    """Relay Sam's message to Alex and run the intent/matching/draft pipeline.
    Runs as a background task so /friend/send returns instantly (the slow LLM
    calls no longer block the dashboard). friend_event_id is the already-
    inserted friend_message event this text came from — tagged with its
    detected language once classification runs, so later short/ambiguous
    messages in the thread can inherit it instead of re-guessing."""
    manager = ConversationManager(db_pool)
    whatsapp = WhatsAppClient()

    # Relay to Alex's WhatsApp as plain text (reads like a normal conversation).
    emit("relaying", "📡 Relaying Sam's message to Alex's WhatsApp")
    await whatsapp.send_message(to=ALEX_NUMBER, text=text)

    # A follow-up picking from the people we just suggested ("connect me with
    # John and Sally", "the second one works, send details") is resolved
    # directly against the last draft's matches — no reclassify/rematch — and
    # still requires Alex's approval before any phone/email goes out.
    if await _handle_followup_selection(db_pool, thread_id, text, whatsapp):
        return

    # A short confirmation ("yeah") immediately after Alex asked a clarifying
    # question ("Oh you mean AI consulting?") means: run matching on what
    # Alex asked, not on Sam's short "yeah" — the classifier alone can't see
    # that confirmation, since it only ever looks at Sam's raw text.
    if _looks_like_affirmation(text):
        emit("checking", "🔍 That looks like a 'yes' to Alex's earlier question")
        clarification = await manager.get_last_open_alex_question(thread_id)
        if clarification:
            effective_request = clarification.rstrip("?").strip()
            slog(f"[Friend] Confirmed clarification -> matching on: {effective_request}")
            await _run_matching_and_push_draft(
                db_pool, thread_id, whatsapp,
                request_text=effective_request, display_text=effective_request,
            )
            return

    # Intent classification (LLM) and keyword filtering (DB) don't depend on
    # each other, but used to run strictly in sequence — kick them off
    # together so the DB round-trip is hidden inside the LLM call's latency
    # instead of adding to it. If intent turns out negative, the fetched
    # candidates are simply discarded (a cheap query to have run for nothing).
    classifier = IntentClassifier()
    engine = MatchingEngine(db_pool)
    classify_failed = False
    emit("intent", "🧠 Asking the AI: is this a contact request?")

    async def _classify():
        try:
            return await classifier.classify(text), False
        except IntentClassificationError as e:
            slog(f"[Friend] Intent classification unavailable, failing open: {e}")
            emit("intent", "⚠️ AI classifier unreachable — assuming yes, just in case")
            return {"is_request": True, "language": "English", "english_query": text}, True

    (classification, classify_failed), candidates = await asyncio.gather(
        _classify(), engine.keyword_filter.filter_candidates(text)
    )
    is_request = classification["is_request"]
    english_query = classification["english_query"]

    # Language is "sticky": a short, ambiguous message ("anyone else", two
    # words) carries almost no language signal, and re-guessing from scratch
    # on it is exactly what produced replies that randomly switched language
    # mid-conversation. For anything under 4 words, inherit whatever language
    # this thread was most recently confirmed to be in, if any; only trust a
    # fresh detection for messages with enough content to actually judge.
    detected_language = classification["language"]
    if len(text.split()) < 4:
        sticky_language = await manager.get_recent_message_language(thread_id, friend_event_id)
        language = sticky_language or detected_language
    else:
        language = detected_language
    await manager.tag_event_language(friend_event_id, language)

    if not is_request:
        emit("resolved", "🙅 Not a contact request — nothing to do")
        return

    emit("intent", f"🧠 Yes — this is a contact request ({language})")

    # Stage 1 (keyword_filter.filter_candidates above) ran concurrently on
    # Sam's original text, before we knew the language — fine for English,
    # but Stage 1 is a plain keyword match against English contact data, so a
    # non-English message would have found nothing. Re-run it on the English
    # rendering instead; this only costs one extra cheap SQL query (Stage 1
    # has no LLM call), so English messages — the common case — pay nothing.
    if language != "English" and english_query != text:
        slog(f"[Friend] Non-English message ({language}) — re-running Stage 1 on English rendering")
        candidates = await engine.keyword_filter.filter_candidates(english_query)

    await _run_matching_and_push_draft(
        db_pool, thread_id, whatsapp,
        request_text=text, display_text=text, uncertain=classify_failed,
        candidates=candidates, search_query=english_query, language=language,
    )


async def _queue_sam_text(db_pool, background: BackgroundTasks, text: str) -> dict:
    """Shared by /friend/send and /friend/send-media: save the message and
    hand the slow relay+pipeline work to a background task."""
    manager = ConversationManager(db_pool)
    thread = await manager.get_or_create_thread(ALEX_NUMBER)
    thread_id = thread["id"]

    friend_event_id = await manager.add_event(thread_id, "friend_message", {"text": text})
    slog(f"[chat] {FRIEND_NAME} -> Alex: {text}")
    emit("received", f"📩 {FRIEND_NAME} says: \"{text}\"")
    background.add_task(_process_sam_message, db_pool, thread_id, text, friend_event_id)
    return {"status": "queued"}


@router.post("/friend/send")
async def friend_send(request: Request, background: BackgroundTasks):
    """Record Sam's message and return immediately; the relay + LLM pipeline run
    in the background so the dashboard never waits on them."""
    db_pool = request.app.state.db_pool
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return {"error": "text is required"}
    return await _queue_sam_text(db_pool, background, text)


@router.post("/friend/send-media")
async def friend_send_media(request: Request, background: BackgroundTasks, file: UploadFile = File(...)):
    """
    Sam's voice-note/image upload. Transcribes (audio) or describes (image)
    via Groq, then feeds the resulting text through the exact same pipeline
    as a typed message — so a voice note asking for a lawyer triggers a
    suggestion exactly like typing it would.
    """
    from app.services.groq_media import transcribe_audio, describe_image, MediaTranscriptionError

    db_pool = request.app.state.db_pool
    content = await file.read()
    content_type = (file.content_type or "").lower()

    try:
        if content_type.startswith("audio"):
            transcript = await transcribe_audio(content, filename=file.filename or "voice.webm")
            text = f"🎙️ {transcript}"
        elif content_type.startswith("image"):
            description = await describe_image(content, mime_type=content_type)
            text = f"🖼️ {description}"
        else:
            return {"error": f"Unsupported content type: {content_type}"}
    except MediaTranscriptionError as e:
        return {"error": str(e)}

    if not text.strip():
        return {"error": "Transcription came back empty"}

    return await _queue_sam_text(db_pool, background, text)


@router.get("/friend/thread")
async def friend_thread(request: Request):
    """Return the Sam<->Alex conversation events for the friend dashboard."""
    db_pool = request.app.state.db_pool
    manager = ConversationManager(db_pool)
    thread = await manager.get_or_create_thread(ALEX_NUMBER)
    events = await manager.get_recent_events(thread["id"], limit=100)
    return {"thread_id": thread["id"], "events": events}
