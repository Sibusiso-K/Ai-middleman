# AI Middleman

**Model migration — 6 September 2026:** retired Groq defaults have been replaced
with GPT-OSS 20B (text) and Qwen 3.6 27B (images). Existing retired `.env` IDs
migrate with warnings. OpenRouter now uses its own endpoint/key. See the
[migration and verification report](ai-middleman/MODEL-MIGRATION.md), including
the remaining production-security limits. Historical eval scores below have
**not** been re-measured on these replacements.

**A WhatsApp bot that answers "hey, do you know anyone who…" — and never sends a word without its owner's approval.**

Alex has 50,000 professional contacts and a WhatsApp inbox full of people asking to be
introduced to some of them. AI Middleman reads those requests in plain language, finds the
right people, and writes the reply in Alex's own voice — then stops and waits for him to tap
**Send**, **Edit**, or **Skip** on his real phone.

No AI-written message ever reaches a third party unsupervised. That constraint is the point of
the project, not a caveat bolted onto it.

---

## The loop

> **Sam:** *"I need a VP of Leveraged Finance in London who specialises in unitranche deals"*

```
Sam's message ─▶ intent + language ─▶ keyword filter ─▶ LLM ranking ─▶ draft in Alex's voice
                                       50,000 → ≤25      top matches      ↓
                                                                   Alex's real WhatsApp
                                                                   [ Send ] [ Edit ] [ Skip ]
                                                                          ↓
                                                                    Sam gets the reply
```

> **Draft shown to Alex:** *"Hey, I've got just the person — Katherine Chang, Managing Director
> at Meridian Growth Partners in London. Strong unitranche track record, happy to make the intro."*

Alex taps Send. Only then does Sam hear back.

---

## Why two stages

Handing 50,000 contacts to an LLM is not a tuning problem, it's an impossible one — roughly 5M+
tokens per query, well past any context window, and hundreds of dollars a call if it did fit.

So the work is split:

| Stage | Does what | Cost | Time |
|---|---|---|---|
| **1 — Keyword filter** | PostgreSQL regex across 9 contact fields, location-aware, caps at 25 candidates | free | <100ms |
| **2 — LLM ranking** | GPT-OSS 20B scores the shortlist on location, role, seniority, relationship strength | account-dependent | re-benchmark required |
| **3 — Draft** | A separate, focused call writes Alex's reply in his voice and the sender's language | free tier | 1–2s |

Ranking and drafting are two calls on purpose. Merged into one prompt, the 8B model got
overloaded by 25 candidates and periodically returned empty completions. Splitting them fixed it.

---

## What's actually built

- **Human-in-the-loop approval** — Send / Edit / Skip as WhatsApp interactive buttons, with a
  typed `SEND` / `EDIT <text>` / `SKIP` fallback and an optional in-chat Flow form for editing.
- **Multi-turn conversation** — one thread per sender with a full event log, so *"the second one"*,
  *"both of them"*, and *"send me their details"* resolve against what was actually suggested.
  Follow-up selection scores **20/20** on the labeled eval set.
- **Voice notes and images** — transcribed via Whisper / described via a vision model, then fed
  through the identical pipeline. A voice note asking for a lawyer behaves like typing it.
- **Conversational contact updates** — *"Katherine moved to Blackstone"* updates the record and
  writes a before/after row to `contact_change_log` with who said it and the raw message.
- **Configured-provider LLM fallback** — Groq → Featherless → OpenRouter → HuggingFace (HF excluded from ranking), all OpenAI-compatible, so a
  rate limit mid-demo degrades instead of dying.
- **React dashboard** — live pipeline visualization, contacts browser, analytics, and a "Sam"
  simulator so the friend side can be demoed without a second physical phone.
- **CI on every push** — unit tests plus a migration schema check against a real Postgres service.

### Languages: English and Afrikaans

Scoped down deliberately. The pipeline originally attempted all 11 of South Africa's official
languages; live testing surfaced two real failures — the 8B model's isiZulu output was frequently
ungrammatical, and short messages like *"anyone else"* caused the detected language to flip
mid-conversation into a language the chat had never been in. Both are documented in
[`app/services/sa_languages.py`](ai-middleman/app/services/sa_languages.py).

The fix was narrowing scope, not patching around it: two languages that work reliably instead of
eleven where nine are a coin flip. A regex guard catches Nguni text the model tries to mislabel as
Afrikaans (**8/8** on the eval set), and a sticky-language rule stops short replies from re-guessing.

---

## Measured, not vibes

`scripts/run_eval.py` runs a labeled eval set rather than ad hoc manual testing. Latest run
([`tests/eval_report.md`](ai-middleman/tests/eval_report.md)):

| Area | Result |
|---|---|
| Follow-up selection | 20/20 (100%) |
| Language guard | 8/8 (100%) |
| Matching relevance | 10/15 (66.7%) |
| Intent classification | 75% accuracy — 100% recall, 66.7% precision |

Intent classification catches every real request but over-fires on warm chatter
(*"Congrats on the promotion!!"*). Given the design, that's the right way round to be wrong: a
false positive costs Alex one tap on Skip, a false negative loses a real introduction. Matching
relevance is the honest weak spot and the next thing to work on.

---

## Running it

The full setup guide — prerequisites, Meta WhatsApp configuration, seeding 50,000 contacts,
ngrok tunneling — lives in **[`ai-middleman/README.md`](ai-middleman/README.md)**.

The short version:

```bash
cd ai-middleman
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # fill in Meta + Groq credentials
docker compose up -d          # PostgreSQL
python generate_contacts.py && python data/import_contacts.py
uvicorn app.main:app --reload
```

Then `cd frontend && npm install && npm run dev` for the dashboard on `http://localhost:5174`.

On Windows, [`start_demo.bat`](start_demo.bat) brings up database, API, tunnel, and dashboard in one go.

---

## Repository layout

```
ai-middleman/          The application
├── app/
│   ├── routes/        WhatsApp webhook, friend simulator, dashboard API, pipeline feed
│   ├── services/      Intent, keyword filter, LLM agent, drafting, conversation, media
│   └── models/        Pydantic schemas
├── frontend/          React 19 + TanStack Start + Tailwind dashboard
├── migrations/        Numbered SQL, applied in order at startup
├── tests/             Unit tests, labeled eval set, latest eval report
└── scripts/           Eval runner, migration check, DB inspection, demo helpers

reports/               LaTeX technical report, analytics, presentation prep, demo runbook
.github/workflows/     CI — pytest + migration schema check
```

---

## Stack

FastAPI · asyncpg · PostgreSQL 15 · Groq (GPT-OSS 20B) · Featherless · Meta WhatsApp Business
Cloud API · React 19 · TanStack Start · Tailwind 4 · Docker

**No ORM** — asyncpg directly, for async webhook throughput without ORM overhead.
**No LangChain** — raw HTTP to OpenAI-compatible endpoints, so swapping providers is a URL change.
**No vector search** — at 50,000 contacts the keyword filter is fast enough, and embeddings would
add storage, memory, and re-indexing cost for no measured gain.

The earlier **$1–4/month** estimate is historical, not a quote for the migrated
models. Verify current provider credits, pricing and usage before deployment.

---

## Status

Phases 1–5 complete: database and 50k contacts, two-stage matching, WhatsApp end-to-end,
human-in-the-loop approval with dashboard and CI, and scoped multilingual support.

Next: raise matching relevance past 66.7%, tighten intent precision on warm chatter, and move to a
paid or self-hosted LLM tier for anything past demo traffic.

A full LaTeX technical report covering architecture, design decisions, the debugging journey, and
cost analysis is in [`reports/`](reports/).
