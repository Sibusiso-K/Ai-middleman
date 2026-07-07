# Live Demo Runbook — AI Middleman

One page, printable, glance-able mid-demo. Two screens visible to the room: your laptop
(dashboard, Inbox tab) and Alex's phone/web.whatsapp.com projected or held up to camera.

---

## T-minus 15 minutes: pre-flight checklist

Run through this before you walk up, not while the room is watching.

- [ ] Docker Desktop running, `ai-middleman-db-1` container up
- [ ] Backend: `uvicorn app.main:app` healthy — hit `GET /health` in a browser tab, confirm `200`
- [ ] ngrok tunnel bound to `plating-marmalade-outthink.ngrok-free.dev`, forwarding to `:8000`
- [ ] Frontend dashboard loads (`https://ai-middleman.vercel.app/`) and **Inbox tab** shows the Sam↔Alex thread with no stale/leftover test messages from earlier rehearsals (clear or scroll past them — a messy transcript undercuts a clean demo)
- [ ] Alex's WhatsApp (`27736013348`, web.whatsapp.com) open and visible/projectable, chat with the bot number (`27650746242`) open
- [ ] **24-hour window is open**: from Alex's WhatsApp, send any message to the bot number right now (e.g. "ready"). Cloud API free-form sends only work within 24h of Alex's last message — this is the #1 silent-failure risk, do it every single time before demoing, no exceptions
- [ ] Do one silent dry run of the exact script below, 10–15 minutes before you go on, so you know current response latency (Groq is fast, but if it's fallen back to Featherless that day it can take 5–10s — know which one you're getting today)

**If ngrok/tunnel is down and you can't fix it in under a minute:** fall back to the
recorded backup clip (see "If it breaks" at the bottom). Don't troubleshoot live.

---

## The script — what you type, what appears, what you say

### Beat 1 — the ask (happy path)

**You type, as Sam, in the Inbox chat box:**
> `Hey Alex, do you know any good corporate lawyers in London?`

**What happens (narrate this while it's happening, ~2-5s):**
1. Message appears instantly on Alex's real WhatsApp, from the bot number.
2. Behind the scenes: intent classifier confirms it's a request, in English; keyword filter narrows the ~50k contact network down to a shortlist; an LLM ranks and picks the best match; a draft introduction is written in Alex's own voice.
3. Alex's WhatsApp receives a message: **"🤖 Sam is asking for `<name>`'s contact details"** with the drafted intro text underneath, and two buttons: **✅ Send** / **❌ Skip**.

**Say while waiting:**
"So Sam just asked a completely normal, casual question — no special syntax, no
command. The system is now deciding, on its own, whether this is even a contact
request, who the best match is out of thousands of contacts, and writing the
introduction in Alex's voice. That's happening right now, in the background."

**When the draft lands on Alex's phone, hold it up / point at the screen:**
"There it is. Alex didn't have to think, search, or write anything — he just has to
decide: send it, or not."

**Tap ✅ Send on Alex's phone.**

**Back in the dashboard**, the reply appears on Sam's side of the thread within a
couple seconds (dashboard polls automatically — no refresh needed, but glance at it
to be sure). Point at it: "And there's the reply landing back with Sam, in real time,
looking exactly like a normal conversation."

---

### Beat 2 — the follow-up (shows multi-turn memory, your strongest "wow" moment)

**You type, as Sam:**
> `perfect, connect me with them`

**Say before it resolves:**
"Now watch this — I'm not naming anyone, not repeating the request. I'm just saying
'them', the way you'd actually text a friend."

**What happens:** the system resolves "them" against the contact(s) just suggested in
Beat 1 (no fresh matching pass, no re-asking) and pushes Alex a second draft with the
real contact details ready to share.

**Tap ✅ Send.**

**Say:**
"It remembered exactly who we were just talking about — no name needed. That's the
difference between a chatbot that answers one question at a time, and a system that
actually follows a conversation."

---

### Beat 3 — the guard rail (proves it's not reckless)

**You type, as Sam:**
> `hey did you watch the game last night?`

**What happens:** no draft is generated at all — the intent classifier correctly
identifies this as small talk, not a contact request. Alex's WhatsApp stays silent
on this one (no draft notification).

**Say:**
"And just as important — it knows when *not* to act. That was small talk, not a
request, so nothing gets sent to Alex for approval. It's not pattern-matching on
keywords, it's actually deciding intent."

*(Optional, only if time allows and you're feeling confident: reply as Alex directly
on WhatsApp with something like "haha yeah, wild finish" — show it just flows through
as a normal chat, appearing on Sam's side as a plain reply, no draft chrome.)*

---

## Closing line for this section

"Every introduction that goes out is still Alex's decision, one tap at a time — the
AI does the tedious part: remembering, matching, and writing. Alex just approves."

---

## If it breaks (have this ready before you go on)

- **Draft never arrives on Alex's phone after ~10s:** don't stall silently — say
  "looks like our model provider is a little slow today, let's give it a moment" and
  keep talking (explain the pipeline verbally) while it catches up. If it doesn't
  land in 20s, move to backup.
- **Backup plan:** have a 60–90s screen recording of a clean run of Beats 1–2 ready
  to play (recorded during a rehearsal, not staged fresh). Say plainly: "I recorded
  this earlier today running exactly this — let me show you," and play it. Judges
  respect an honest fallback far more than a stalled live demo.
- **Wrong-language / garbled reply appears:** don't panic-narrate the bug live. If it
  happens, name it calmly ("that's actually a great segue — this exact kind of
  language-detection glitch is what I'll talk about in a couple of slides") and keep
  moving. This literally ties into your "What got stuck" slide, so it's recoverable
  either way.
- **24-hour window silently expired (no message reaches Alex at all):** this is the
  most common failure and looks identical to "nothing happening." If nothing arrives
  within 15s of Beat 1, have Alex's phone send **any** message to the bot number
  right now to reopen the window, then retry Beat 1 once, live, saying "let me just
  refresh our session" rather than pretending it didn't happen.

---

## After the demo, before you sit down

Say the closing line above, then transition straight into Slide 5 ("What I learned")
— don't leave a silence after the demo ends, it's the natural high point, ride
straight into the next beat while the room's attention is still up.
