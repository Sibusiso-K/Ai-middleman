# AI Middleman — WhatsApp Contact Matching System

Current model defaults and rollout instructions:
[MODEL-MIGRATION.md](MODEL-MIGRATION.md) (6 September 2026). Old Llama results
and cost estimates in this historical guide do not establish replacement-model
accuracy or current operating cost. A real WhatsApp signing secret is now
required: invalid signatures are rejected, not accepted for debugging.

> Automating business connections through intelligent AI matching.

A WhatsApp bot that reads natural-language contact requests, matches them against a 50,000-contact database using a two-stage AI pipeline, drafts a reply in the account owner's own voice — and then waits for his real approval (Send / Edit / Skip) before anything reaches the requester. Replies in English and Afrikaans (see [Language scope](#language-scope)), with a React dashboard for live-pipeline visualization and analytics.

---

## What It Does

A friend messages Alex asking for an introduction, e.g.:

> *"I need a VP of Leveraged Finance in London who specialises in unitranche deals"*

The system classifies the message, searches Alex's network, ranks the best matches with an LLM, and drafts a reply in Alex's own voice:

> *"Hey, I've got just the person — Katherine Chang, Managing Director at Meridian Growth Partners in London. Strong unitranche track record, happy to make the intro."*

That draft is sent to **Alex on his real WhatsApp** with Send / Edit / Skip buttons — nothing goes out to the requester until he approves it. No AI-generated message ever reaches a third party unsupervised.

---

## Architecture

```
Friend's WhatsApp message
      │
      ▼
Intent + language classification (app/services/intent_classifier.py)
      │  Groq Llama 3.1 8B, Featherless fallback · one call detects
      │  intent, language (11 SA official languages), and an English
      │  gloss for search
      │
      ├── Not a contact request → nothing happens
      │
      ▼ Contact request
Stage 1: Keyword filter (app/services/keyword_filter.py)
      │  PostgreSQL · 50,000 contacts → ≤25 candidates
      │
      ▼
Stage 2: LLM ranking (app/services/agent.py)
      │  Confidence scoring · ranked reasoning
      │
      ▼
Draft generation (app/services/draft_generator.py)
      │  Writes Alex's reply in his own voice and in the sender's language
      │
      ▼
Alex approves on his real WhatsApp (Send / Edit / Skip)
      │  app/routes/whatsapp_webhook.py handles Alex's response
      │
      ▼
WhatsApp Client (app/services/whatsapp_client.py)
      Meta Graph API · approved reply sent
```

A separate `frontend/` (React + TanStack) talks to `app/routes/dashboard_api.py` for live pipeline visualization, contacts browsing, and analytics — plus a "Sam" simulator (`app/routes/friend.py`) for demoing the friend side of a conversation without a second physical phone.

---

## Key Design Decisions

| Decision | Chosen | Alternative | Reason |
|---|---|---|---|
| Database | PostgreSQL | MongoDB | Relational integrity, free self-hosted |
| API Framework | FastAPI | Flask/Django | Async, fast, auto-docs |
| DB Driver | asyncpg | SQLAlchemy | Pure async, no ORM overhead |
| LLM Provider | Groq (Llama 3.1 8B), Featherless fallback | OpenAI/Anthropic | Groq's LPU hardware is fast + free-tier; Featherless takes over automatically if Groq's rate limit is hit mid-session |
| Vector Search | ❌ Not used | pgvector | 50k contacts fits in keyword filter |
| Embeddings | ❌ Not used | SentenceTransformers | Adds memory pressure, not needed |
| LLM Framework | Raw HTTP | LangChain | Simpler, fewer dependencies |
| Matching vs. drafting | Two separate LLM calls | One merged "rank + draft" call | The merged prompt got too large for an 8B model with 25 candidates and sometimes returned empty completions — splitting into two focused calls fixed it |

**Why two stages?** Sending 50,000 contacts directly to an LLM is impossible — it would exceed context windows and cost hundreds of dollars per query. The keyword filter reduces the problem to at most 25 candidates, which fit comfortably in a single LLM prompt at zero cost.

---

## Project Structure

```
ai-middleman/
├── app/
│   ├── main.py                     # FastAPI entrypoint, startup, /health, /match
│   ├── database.py                 # asyncpg connection pool, migration runner
│   ├── models/
│   │   └── schemas.py              # Pydantic models
│   ├── routes/
│   │   ├── whatsapp_webhook.py     # Alex's replies: Send/Edit/Skip + free text
│   │   ├── friend.py               # "Sam" (the friend) side: /friend/send, /friend/send-media
│   │   ├── dashboard_api.py        # Contacts, analytics, activity feed for the frontend
│   │   └── pipeline.py             # Live pipeline event stream for the dashboard
│   └── services/
│       ├── intent_classifier.py    # Intent + language detection + English gloss, one LLM call
│       ├── keyword_filter.py       # Stage 1: SQL keyword + location filter
│       ├── agent.py                # Stage 2: LLM ranking (Groq, Featherless fallback)
│       ├── matching_engine.py      # Orchestrates Stage 1 → Stage 2
│       ├── draft_generator.py      # Writes Alex's reply, in the sender's language
│       ├── conversation_manager.py # Thread/event log for multi-turn conversations
│       ├── response_formatter.py   # JSON → privacy-redacted WhatsApp text
│       ├── whatsapp_client.py      # Meta Graph API client (text, buttons, Flows)
│       ├── groq_media.py           # Voice transcription (Whisper) + image description
│       ├── llm_provider.py         # Picks Groq vs Featherless per call
│       ├── llm_json.py             # Tolerant JSON parsing for LLM replies
│       ├── sa_languages.py         # Supported reply languages (English, Afrikaans)
│       ├── contact_lookup.py       # Fuzzy name resolution, shared by updates + direct lookup
│       ├── update_extractor.py     # "Katherine moved to Blackstone" → contact update + audit row
│       └── pipeline_events.py      # In-memory stage feed powering the dashboard visualizer
├── frontend/                       # React + TanStack dashboard (the demo surface)
├── migrations/                     # Numbered SQL migrations, applied in order at startup
├── tests/
│   ├── test_matching.py            # Unit tests: keyword tokenization, response formatting
│   ├── test_migrations.py          # Spins up a scratch DB, verifies schema shape
│   ├── eval_set.json               # Labeled intent/matching evaluation cases
│   └── eval_report.md              # Latest run_eval.py output
├── scripts/                        # check_db.py, debug_draft.py, simulate_friend_message.py, run_eval.py
├── reports/                        # LaTeX technical report + presentation prep
├── generate_contacts.py            # Synthetic contact data generator
├── dev_tunnel.py                   # ngrok tunnel for local webhook testing
├── docker-compose.yml              # PostgreSQL service
├── .env.example                    # Environment variable template
└── README.md                      # This file
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Docker Desktop
- A Meta WhatsApp Business API account
- A Featherless.ai API key (free at featherless.ai)

### 1. Clone and set up environment

```bash
git clone https://github.com/Sibusiso-K/Ai-middleman.git
cd Ai-middleman/ai-middleman
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your actual values
```

### 3. Start the database

```bash
docker compose up -d
```

### 4. Generate and import contact data

```bash
# Generate synthetic contacts (or replace with your real CSV)
python generate_contacts.py

# Import to PostgreSQL
python data/import_contacts.py
```

Verify:
```bash
docker exec -it ai-middleman-db-1 psql -U postgres -d aimiddleman -c "SELECT COUNT(*) FROM contacts;"
# Expected: 50000
```

### 5. Start the API

```bash
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/health` — should return `{"status":"ok"}`

### 6. Test the matching engine

```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"query": "I need a credit finance specialist in London"}'
```

### 7. Start the dashboard

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5174`. This is the live pipeline view, contacts browser, analytics, and the "Sam" friend simulator for demoing without a second phone.

### 8. Set up WhatsApp webhook (for full end-to-end)

```bash
# Start ngrok tunnel
python dev_tunnel.py
```

Copy the printed URL and configure it in your Meta Developer dashboard as the Callback URL. See [WhatsApp Setup Guide](#whatsapp-setup) below.

---

## WhatsApp Setup

1. Create a Meta Developer account at [developers.facebook.com](https://developers.facebook.com)
2. Create a new app → choose **Business** type → add **WhatsApp** product
3. Go to **Step 1. Try it out** → generate an access token → copy your Phone Number ID
4. Go to **Step 2. Production setup** → Configure Webhooks:
   - Callback URL: `https://your-ngrok-url.ngrok-free.app/webhook/whatsapp`
   - Verify token: same as `WHATSAPP_VERIFY_TOKEN` in your `.env`
5. Subscribe to the **messages** webhook field
6. Register a dedicated business phone number
7. Generate a permanent access token and update `.env`
8. Publish your app (requires a privacy policy URL)

---

## Matching Pipeline — How It Works

### Intent + language classification
One LLM call decides whether the message is a contact request, detects whether it's written in English or Afrikaans (or a natural code-switched mix), and produces an English rendering for search — all in a single round trip, so English messages (the common case) pay no extra latency.

### Language scope
Supported reply languages are **English and Afrikaans**, deliberately — not all 11 of South Africa's official languages.

The pipeline originally attempted all 11. Live testing surfaced two real failure modes, both on the Nguni family (isiZulu, isiXhosa, siSwati, isiNdebele):

1. **Garbled output.** Even when isiZulu was correctly identified, the 8B model's isiZulu was frequently not grammatical isiZulu — consistent with those languages being far less represented in training data than English or Afrikaans.
2. **Mid-conversation language flips.** Short, ambiguous messages ("anyone else") were sometimes misclassified into one of those languages, producing a nonsensical reply in a chat that had been English throughout.

Both were fixed by narrowing scope rather than patching around it — two languages that work reliably beat eleven where nine are a coin flip. Two guards remain in code: a Nguni-marker regex (`_looks_nguni_not_afrikaans` in `intent_classifier.py`) that overrides the model when it force-fits real isiZulu into the "Afrikaans" bucket, and a sticky-language rule so short follow-ups inherit the prior message's language instead of re-guessing. The language guard scores 8/8 on the eval set.

See `app/services/sa_languages.py` for the full rationale.

### Stage 1: Keyword Filter
Extracts 3+ character tokens from the (English-rendered) query and searches across 9 database fields using PostgreSQL regex, capped at 25 candidates. Location-aware: queries containing city or country names boost geographically matching contacts to the top of the candidate list before passing to the LLM.

### Stage 2: LLM Agent
Sends the candidates to Llama 3.1 8B via Groq (Featherless as an automatic fallback) with a structured prompt enforcing scoring rules — location match, role/skill alignment, seniority, relationship strength, and VIP status as a tiebreaker. Only matches at confidence ≥ 0.5 are considered viable.

### Draft generation and approval
A second, focused LLM call drafts Alex's reply — in the sender's own language, continuing the conversation naturally instead of opening with a generic greeting every time. The draft is sent to Alex's real WhatsApp with Send / Edit / Skip buttons; nothing reaches the requester until he approves it.

---

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `DB_PASSWORD` | PostgreSQL password | ✅ |
| `WHATSAPP_PHONE_NUMBER_ID` | From Meta dashboard | ✅ |
| `WHATSAPP_ACCESS_TOKEN` | Permanent token from Meta | ✅ |
| `WHATSAPP_APP_SECRET` | From App Settings → Basic | ✅ |
| `WHATSAPP_VERIFY_TOKEN` | Any string you choose | ✅ |
| `GROQ_API_KEY` | From console.groq.com/keys — primary LLM provider | ✅ |
| `FEATHERLESS_API_KEY` | From featherless.ai — automatic fallback if Groq's free-tier rate limit is hit | ✅ (for resilience) |
| `BUSINESS_PHONE_NUMBER` | Your Cloud API number | ✅ |
| `ALEX_WHATSAPP_NUMBER` | The account owner's real WhatsApp number | ✅ |
| `WHATSAPP_EDIT_FLOW_ID` | Enables the in-chat "Edit draft" Flow form | ❌ |
| `NGROK_DOMAIN` / `NGROK_AUTHTOKEN` | For `dev_tunnel.py` during local development | ❌ |

See `.env.example` for the full list, including per-service LLM timeout/retry tuning.

---

## Cost

| Component | Cost |
|---|---|
| PostgreSQL (self-hosted) | $0 |
| LLM API (Groq + Featherless free tiers) | $0 |
| Hosting (Oracle Cloud Free Tier) | $0 |
| WhatsApp Business API | $0–3/month |
| Domain + SSL | $1/month |
| **Total** | **$1–4/month** |

Free-tier LLM APIs are the main scaling constraint today — a paid tier or self-hosted model is the natural next step if usage grows beyond what Groq/Featherless's free rate limits comfortably support.

---

## Running Tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v           # All unit and mocked provider/security tests
python scripts/check_llm.py          # Configured model catalogues, no inference
python scripts/check_llm.py --probe  # Small synthetic text calls; may consume credits
python scripts/test_migrations.py     # Spins up a scratch DB, verifies schema shape
python scripts/run_eval.py            # Labeled intent/matching accuracy (needs the API running)
```

`run_eval.py` measures real accuracy against a labeled test set (`tests/eval_set.json`) instead of relying on ad hoc manual testing — see `tests/eval_report.md` for the latest run. Both test suites above run automatically in CI on every push (see `.github/workflows/tests.yml`).

---

## Roadmap

- [x] Phase 1: PostgreSQL database, 50,000 contacts, FastAPI foundation
- [x] Phase 2: Two-stage matching engine (keyword filter + LLM agent)
- [x] Phase 3: WhatsApp Business API integration, end-to-end message flow
- [x] Phase 4: Human-in-the-loop approval (Send/Edit/Skip), React dashboard, labeled evaluation harness, CI
- [x] Phase 5: Multilingual support, scoped to English + Afrikaans after live testing found the 8B model unreliable on the Nguni languages — see [Language scope](#language-scope) and `/reports`
- [ ] Phase 6: Raise matching relevance past 66.7% and intent precision past 66.7%; native-speaker-reviewed evaluation set as a prerequisite for widening the language set; paid/self-hosted LLM tier for production scale

---

## Technical Report

A full LaTeX technical report documenting the architecture, design decisions, debugging journey, and cost analysis is available in the `/reports` directory.

---

## Built With

- [FastAPI](https://fastapi.tiangolo.com/) — API framework
- [asyncpg](https://magicstack.github.io/asyncpg/) — PostgreSQL async driver
- [Groq](https://groq.com/) — primary LLM inference (Llama 3.1 8B), fast free-tier hardware
- [Featherless.ai](https://featherless.ai/) — automatic LLM fallback
- [Meta WhatsApp Business Cloud API](https://developers.facebook.com/docs/whatsapp) — Messaging
- [PostgreSQL](https://www.postgresql.org/) — Database
- [Docker](https://www.docker.com/) — Containerisation
- [React](https://react.dev/) + [TanStack](https://tanstack.com/) — Dashboard
- [ngrok](https://ngrok.com/) — Local webhook tunneling (dev only)
