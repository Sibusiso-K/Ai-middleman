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
from app.services.contact_lookup import resolve_contact_by_name
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


# Title-Case name sequences ("Aaron Acosta"), used to guard the "send me
# their details" fallback below: without this, "Do you know Aaron Acosta? Do
# you have his details?" was being hijacked by the generic details-request
# fallback and handed the details of whoever was last sent (a stale, unrelated
# contact from earlier in the thread) instead of reaching the named-contact
# lookup — because the fallback only ever looked at "last sent match", never
# at whether the message actually named someone else entirely.
_PROPER_NAME_RE = re.compile(r"\b([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+)+)\b")


def _mentions_unmatched_name(text: str, matches: list) -> bool:
    """True if text contains a full name that isn't one of the currently
    suggested matches — signals Sam is asking about someone NEW, so the
    generic "resend last details" fallback must not claim this message."""
    found = _PROPER_NAME_RE.findall(text)
    if not found:
        return False
    known_first_names = {
        (m.get("name") or "").split()[0].lower()
        for m in matches if m.get("name")
    }
    return any(name.split()[0].lower() not in known_first_names for name in found)


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


_GROUP_PRONOUN_RE = re.compile(
    r"\b(both|all three|them all|everyone|all of (them|those|em)|them|dem|em|those|these)\b",
    re.IGNORECASE,
)


def _resolve_selected_contacts(text: str, matches: list) -> list:
    """Given Sam's follow-up and the 1-3 previously-suggested matches, return
    the subset Sam is picking — by name ("connect me with John and Sally"), by
    position ("the second one"), or all ("both of them" / "them" / "em",
    misspelled connecting verb and all — "acount with them" resolves the same
    as "connect me with them"). Returns [] if the message doesn't clearly
    point at a suggested contact, or reads as a rejection rather than a pick."""
    if not matches:
        return []
    if _NEGATIVE_CUE_RE.search(text):
        return []

    low = f" {text.lower()} "
    is_question = text.rstrip().endswith("?")

    # A bare group pronoun ("them"/"dem"/"em"/"those"/"these") or an explicit
    # group phrase ("both of them", "all three") is self-sufficient — it does
    # NOT need a correctly-spelled connect/send verb next to it, since typos
    # on that verb ("acount with them") are exactly what this needs to
    # tolerate. The only thing that still gates it is: a genuine QUESTION
    # ("what about them?", "are they any good?") isn't a pick, so if the
    # message ends in "?" it still needs a positive cue to count as one.
    if _GROUP_PRONOUN_RE.search(low):
        if is_question and not _POSITIVE_CUE_RE.search(text):
            return []
        return list(matches)

    # Everything below (a position or a name) can also appear in a question
    # ("what about the second one?"), so it only counts as a pick when there's
    # a positive cue and no rejection.
    if not _POSITIVE_CUE_RE.search(text):
        return []

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
    # But NOT if the message names someone else entirely ("Do you know Aaron
    # Acosta? Do you have his details?") — that's a fresh named-contact
    # question, not a request to resend the last person's details.
    if not selected and _looks_like_details_request(text) and not _mentions_unmatched_name(text, matches):
        last = await manager.get_last_sent_match(thread_id)
        if last:
            selected = [last]

    if not selected:
        return False  # not a pick — fall through to the normal pipeline

    emit("checking", "🔍 Sam is picking from the people we suggested")

    # Look up real contact details for each selected person. Fetch title and
    # company fresh from the DB so that a contact who was updated since the
    # last draft suggestion shows the current employer, not the stale one
    # stored in the match-stub event payload.
    picked = []
    async with db_pool.acquire() as conn:
        for m in selected:
            cid = m.get("contact_id")
            if not cid:
                continue
            c = await conn.fetchrow(
                "SELECT full_name, title, company, phone, email FROM contacts WHERE id = $1", cid
            )
            if not c or not (c["phone"] or c["email"]):
                continue
            details = " / ".join(filter(None, [
                f"📞 {c['phone']}" if c["phone"] else None,
                f"📧 {c['email']}" if c["email"] else None,
            ]))
            first = c["full_name"].split()[0] if c["full_name"] else "them"
            picked.append({
                "match": m,
                "full_name": c["full_name"],
                "first": first,
                "details": details,
                "title": c["title"],
                "company": c["company"],
            })

    if not picked:
        return False  # couldn't resolve any real details — let the pipeline try

    generator = DraftGenerator()
    contacts_for_draft = [
        {"full_name": p["full_name"], "details_str": p["details"],
         "title": p["title"], "company": p["company"]}
        for p in picked
    ]
    draft = await generator.generate_details_draft(contacts_for_draft)

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


async def _handle_named_contact_lookup(
    db_pool, thread_id: int, text: str, whatsapp: "WhatsAppClient", named_contact: str
) -> None:
    """Handle a direct "do you know <Name>?" style request — a lookup by
    identity, not by role/skill/sector. This is deliberately NOT run through
    Stage 1/2 matching: that pipeline's LLM scoring is built entirely around
    role/sector relevance and caps anything that isn't a role match below
    0.5, so a real named contact would score low and get dropped even when
    they're sitting right there in the database. Instead this does a direct
    fuzzy name lookup and pushes Alex a Send/Skip-gated draft — same PII
    discipline as _handle_followup_selection: phone/email are only included
    in the draft text if Sam's message itself asked for details, otherwise
    the draft just confirms the contact exists and offers to share more."""
    manager = ConversationManager(db_pool)
    emit("named_lookup", f"🔍 Looking up {named_contact} directly")

    async with db_pool.acquire() as conn:
        contact = await resolve_contact_by_name(conn, named_contact)

    if not contact:
        draft = f"Hmm, I don't think I know a {named_contact} in my network — might be able to help with something else though!"
        event_id = await manager.add_event(thread_id, "draft_suggested", {
            "original_message": text,
            "draft_reply": draft,
            "matches": [],
        })
        buttons = [
            {"type": "reply", "reply": {"id": f"send_{event_id}", "title": "✅ Send"}},
            {"type": "reply", "reply": {"id": f"skip_{event_id}", "title": "❌ Skip"}},
        ]
        draft_body = (
            f"🤖 *{FRIEND_NAME} asked about {named_contact}*\n\n"
            f"*Draft:* {draft}\n\n"
            f"Tap Send to use it as-is, or Skip to hold off."
        )
        await whatsapp.send_interactive_buttons(to=ALEX_NUMBER, body_text=draft_body, buttons=buttons)
        emit("awaiting_approval", "📤 Sent to Alex for approval — waiting for Send/Skip")
        return

    full_name = contact["full_name"]
    first = full_name.split()[0] if full_name else named_contact
    role_bits = " / ".join(filter(None, [contact.get("title"), contact.get("company")]))
    role_note = f" — {role_bits}" if role_bits else ""

    # Always send a confirmation first ("Yeah I know Kara, she's Partner at Bain
    # Capital. That who you're after?") rather than jumping straight to details.
    # The two-step flow is more conversational and lets Sam correct a wrong match
    # before PII goes out. Once Sam says "yes" / "yeah" / "send her details",
    # the affirmation path or followup-selection path sends the actual details.
    draft = f"Yeah I know {first}{role_note}. That who you're after?"

    match_stub = [{
        "contact_id": contact["id"],
        "name": full_name,
        "title": contact.get("title"),
        "company": contact.get("company"),
        "location": contact.get("location"),
    }]
    event_id = await manager.add_event(thread_id, "draft_suggested", {
        "original_message": text,
        "draft_reply": draft,
        "matches": match_stub,
        # Flag used by affirmation path to know "yeah" here means "yes, send
        # me their details" rather than "yes to Alex's matching question".
        "draft_type": "named_contact_confirmation",
    })
    buttons = [
        {"type": "reply", "reply": {"id": f"send_{event_id}", "title": "✅ Send"}},
        {"type": "reply", "reply": {"id": f"skip_{event_id}", "title": "❌ Skip"}},
    ]
    draft_body = (
        f"🤖 *{FRIEND_NAME} asked about {full_name}*\n\n"
        f"*Draft:* {draft}\n\n"
        f"Tap Send to confirm, or Skip to hold off."
    )
    await whatsapp.send_interactive_buttons(to=ALEX_NUMBER, body_text=draft_body, buttons=buttons)
    emit("awaiting_approval", "📤 Confirmation sent to Alex — waiting for Send/Skip")


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
    # 0.7 (not 0.5) is the bar for "directly related" — matches agent.py's own
    # CONFIDENCE SCORE GUIDE, where 0.7-0.89 is the first band that "genuinely
    # does the requested role/sector" rather than merely being adjacent to it
    # (0.5-0.69 is explicitly a "partial match" band: right role but off on
    # location/seniority). Below that, Sam should be asked a clarifying
    # question instead of being confidently pointed at a loose fit.
    viable = [m for m in all_matches if m.get("confidence", 0) >= 0.7]
    emit("matching", f"🔗 Found {len(viable)} strong match(es)" if viable else "🔗 No directly-related match found")

    clarification_question = (result.get("clarification_question") or "").strip()
    if viable:
        # The separate DraftGenerator call below writes the "here are some
        # people" message in Alex's voice.
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
    elif clarification_question:
        # Nothing cleared the "directly related" bar, but the matching LLM
        # flagged real ambiguity (match_quality weak/none) and gave a
        # specific question rather than a bare rejection — surface that
        # instead of the generic "nothing great" line, so Sam can narrow
        # down the request rather than the system silently guessing.
        emit("drafting", "✍️ Asking a clarifying question instead of guessing")
        draft = clarification_question
    else:
        emit("drafting", "✍️ No match and no clarification offered — using fallback")
        draft = "Nothing great in my network for this one — let me ask around and get back to you 🤔"

    event_id = await manager.add_event(thread_id, "draft_suggested", {
        "original_message": request_text,
        "draft_reply": draft,
        # Only store matches that actually cleared the viability bar — Sam
        # was told about these (or told "nothing great"), so a follow-up like
        # "connect me with the first one" must never resolve positionally
        # into a sub-threshold contact that was silently rejected. Storing
        # all_matches here let exactly that happen: "nothing great in my
        # network" followed by "connect me with the first one" would still
        # draft a confident intro to the contact that was just rejected.
        "matches": viable,
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

    # A short confirmation ("yeah") could mean two different things depending on
    # what the last draft was:
    #   A) The last draft was a named-contact confirmation ("Yeah I know Kara,
    #      that who you're after?") — Sam's "yeah" means "yes, send me their
    #      details." Generate and push the actual details draft.
    #   B) Alex asked a clarifying question ("Oh you mean AI consulting?") and
    #      Sam is confirming — run matching on Alex's phrasing instead of Sam's
    #      short "yeah."
    if _looks_like_affirmation(text):
        emit("checking", "🔍 That looks like a 'yes'")

        last_payload = await manager.get_last_draft_payload(thread_id)
        if last_payload and last_payload.get("draft_type") == "named_contact_confirmation":
            matches = last_payload.get("matches") or []
            if matches:
                m = matches[0]
                cid = m.get("contact_id")
                if cid:
                    async with db_pool.acquire() as conn:
                        c = await conn.fetchrow(
                            "SELECT full_name, title, company, phone, email FROM contacts WHERE id = $1", cid
                        )
                    if c and (c["phone"] or c["email"]):
                        details_str = " / ".join(filter(None, [
                            f"📞 {c['phone']}" if c["phone"] else None,
                            f"📧 {c['email']}" if c["email"] else None,
                        ]))
                        generator = DraftGenerator()
                        draft = await generator.generate_details_draft([{
                            "full_name": c["full_name"],
                            "details_str": details_str,
                            "title": c["title"],
                            "company": c["company"],
                        }])
                        emit("named_lookup", f"🔍 Sam confirmed — pulling {c['full_name'].split()[0]}'s details")
                        event_id = await manager.add_event(thread_id, "draft_suggested", {
                            "original_message": text,
                            "draft_reply": draft,
                            "matches": matches,
                        })
                        buttons = [
                            {"type": "reply", "reply": {"id": f"send_{event_id}", "title": "✅ Send"}},
                            {"type": "reply", "reply": {"id": f"skip_{event_id}", "title": "❌ Skip"}},
                        ]
                        who = c["full_name"]
                        draft_body = (
                            f"🤖 *{FRIEND_NAME} confirmed — here are {who.split()[0]}'s details*\n\n"
                            f"*Draft:*\n{draft}\n\n"
                            f"Tap Send to share, or Skip to hold off."
                        )
                        await whatsapp.send_interactive_buttons(to=ALEX_NUMBER, body_text=draft_body, buttons=buttons)
                        emit("awaiting_approval", f"📤 Details draft sent to Alex — waiting for Send/Skip")
                        return

        # Case B: "yes" to Alex's clarifying question ("Oh you mean AI consulting?")
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
            return {"is_request": True, "is_update": False, "update_target": None, "named_contact": None, "language": "English", "english_query": text}, True

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

    is_update = classification.get("is_update", False)
    if is_update:
        # Intent classifier flags the update; a dedicated LLM call extracts
        # the precise {contact_name, attribute, new_value} — better accuracy
        # than asking the 5-in-1 intent prompt to do both jobs at once.
        from app.services.update_extractor import extract_update_target
        emit("updating", "✏️ Extracting update details…")
        update_target = await extract_update_target(text)
        contact_name = update_target.get("contact_name")
        attribute = update_target.get("attribute", "")
        new_value = update_target.get("new_value", "")
        who = contact_name or "your own record"
        emit("updating", f"✏️ Update proposed: {who} → {attribute} = {new_value!r}")

        # Store the pending update so the webhook can apply it on Alex's tap.
        await manager.add_event(thread_id, "update_pending", {
            "source_message": text,
            "update_target": update_target,
        })

        # Ask Alex to confirm before touching the DB.
        display_who = contact_name if contact_name else "your record"
        prompt = (
            f"📋 *{FRIEND_NAME} says:* \"{text}\"\n\n"
            f"Update {display_who}'s *{attribute}* to: *{new_value}*?"
        )
        await whatsapp.send_interactive_buttons(
            to=ALEX_NUMBER,
            body_text=prompt,
            buttons=[
                {"type": "reply", "reply": {"id": "update_yes", "title": "✅ Update"}},
                {"type": "reply", "reply": {"id": "update_no",  "title": "❌ Ignore"}},
            ],
        )
        emit("update_approval", f"⏳ Waiting for Alex to approve update to {who}'s {attribute}")
        return

    if not is_request:
        emit("resolved", "🙅 Not a contact request — nothing to do")
        return

    named_contact = classification.get("named_contact")
    if named_contact:
        # Asking about ONE specific named person ("Do you know Aaron
        # Aguirre?") is an identity lookup, not a role/sector search — skip
        # Stage 1/2 matching entirely (its LLM scoring would wrongly cap this
        # below the viable threshold since there's no role to match against).
        emit("intent", f"🧠 Yes — asking about a specific contact: {named_contact}")
        await _handle_named_contact_lookup(db_pool, thread_id, text, whatsapp, named_contact)
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
