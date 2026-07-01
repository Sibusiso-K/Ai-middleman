# AI Middleman — WhatsApp Contact Matching System

> Automating business connections through intelligent AI matching.

A production-grade WhatsApp bot that receives natural language connection requests and automatically matches them against a database of professional contacts using a two-stage AI pipeline — returning ranked results with confidence scores and reasoning in under 3 seconds.

---

## What It Does

Send a WhatsApp message like:

> *"I need a VP of Leveraged Finance in London who specialises in unitranche deals"*

And receive back:

> **1. Katherine Chang** — Managing Director at Meridian Growth Partners, London (95%)
> ✅ Direct match: leveraged finance expertise, London-based, strong relationship

Fully automated. No human in the loop.

---

## Architecture

```
WhatsApp Message
      │
      ▼
FastAPI Webhook (app/routes/whatsapp_webhook.py)
      │
      ├── Stage 1: Keyword Filter (app/services/keyword_filter.py)
      │     └── PostgreSQL · 50,000 contacts → 30-50 candidates
      │     └── Location-aware SQL ordering
      │
      ├── Stage 2: LLM Agent (app/services/agent.py)
      │     └── Featherless.ai · Llama 3.1 8B (free tier)
      │     └── Confidence scoring · Ranked reasoning
      │
      ├── Response Formatter (app/services/response_formatter.py)
      │     └── JSON → WhatsApp-ready text
      │
      └── WhatsApp Client (app/services/whatsapp_client.py)
            └── Meta Graph API · Reply sent
```

---

## Key Design Decisions

| Decision | Chosen | Alternative | Reason |
|---|---|---|---|
| Database | PostgreSQL | MongoDB | Relational integrity, free self-hosted |
| API Framework | FastAPI | Flask/Django | Async, fast, auto-docs |
| DB Driver | asyncpg | SQLAlchemy | Pure async, no ORM overhead |
| LLM Provider | Featherless.ai | OpenAI/Anthropic | Free tier, Llama 3.1 8B |
| Vector Search | ❌ Not used | pgvector | 50k contacts fits in keyword filter |
| Embeddings | ❌ Not used | SentenceTransformers | Adds memory pressure, not needed |
| LLM Framework | Raw HTTP | LangChain | Simpler, fewer dependencies |

**Why two stages?** Sending 50,000 contacts directly to an LLM is impossible — it would exceed context windows and cost hundreds of dollars per query. The keyword filter reduces the problem to 30-50 candidates, which fit comfortably in a single LLM prompt at zero cost.

---

## Project Structure

```
ai-middleman/
├── app/
│   ├── main.py                    # FastAPI entrypoint, startup, routes
│   ├── database.py                # asyncpg connection pool, migration runner
│   ├── models/
│   │   └── schemas.py             # Pydantic models
│   ├── routes/
│   │   └── whatsapp_webhook.py    # Webhook receiver (GET verify + POST handler)
│   └── services/
│       ├── keyword_filter.py      # Stage 1: Local keyword + location filter
│       ├── agent.py               # Stage 2: LLM agent via Featherless.ai
│       ├── matching_engine.py     # Orchestrates Stage 1 → Stage 2
│       ├── response_formatter.py  # JSON → WhatsApp text formatter
│       └── whatsapp_client.py     # Meta Graph API client
├── data/
│   └── import_contacts.py         # CSV → PostgreSQL importer
├── dashboard/
│   └── app.py                     # Streamlit dashboard (4 pages)
├── migrations/
│   └── 001_create_tables.sql      # Database schema
├── tests/
│   ├── test_keyword_filter.py     # Keyword filter unit tests
│   └── test_matching_engine.py    # End-to-end pipeline tests
├── reports/                       # LaTeX technical report
├── generate_contacts.py           # Synthetic contact data generator
├── dev_tunnel.py                  # ngrok tunnel for local webhook testing
├── docker-compose.yml             # PostgreSQL + Ollama services
├── .env.example                   # Environment variable template
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
cd Ai-middleman
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

### 7. Start the dashboard (optional)

```bash
cd dashboard
streamlit run app.py
```

Visit `http://localhost:8501`

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

### Stage 1: Keyword Filter
Extracts 3+ character tokens from the query and searches across 9 database fields using PostgreSQL regex. Location-aware: queries containing city or country names boost geographically matching contacts to the top of the candidate list before passing to the LLM.

### Stage 2: LLM Agent
Sends the 30-50 candidates to Llama 3.1 8B via Featherless.ai with a structured prompt enforcing strict scoring rules:

1. **Location match** (most important) — wrong location caps confidence at 0.6
2. **Role/skill match** — title, expertise, can_help_with alignment
3. **Seniority** — Partner/MD preferred over Analyst/Associate
4. **Relationship strength** — 4-5 preferred over 1-2
5. **VIP status** — tiebreaker

### Response Formatting
- **Good match** (>0.7): Returns top 5 with full reasoning and confidence bars
- **Weak match** (0.4-0.7): Returns top 3 with caveat
- **No match** (<0.4): Asks a clarifying question

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
| `FEATHERLESS_API_KEY` | From featherless.ai | ✅ |
| `OLLAMA_URL` | Local fallback LLM | ❌ |

---

## Cost

| Component | Cost |
|---|---|
| PostgreSQL (self-hosted) | $0 |
| LLM API (Featherless.ai free tier) | $0 |
| Hosting (Oracle Cloud Free Tier) | $0 |
| WhatsApp Business API | $0–3/month |
| Domain + SSL | $1/month |
| **Total** | **$1–4/month** |

---

## Running Tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

---

## Roadmap

- [x] Phase 1: PostgreSQL database, 50,000 contacts, FastAPI foundation
- [x] Phase 2: Two-stage matching engine (keyword filter + LLM agent)
- [x] Phase 3: WhatsApp Business API integration, end-to-end message flow
- [ ] Phase 4: Oracle Cloud deployment, SSL, permanent webhook, monitoring
- [ ] Phase 5: Feedback loop, contact scoring over time, admin dashboard

---

## Technical Report

A full LaTeX technical report documenting the architecture, design decisions, debugging journey, and cost analysis is available in the `/reports` directory.

---

## Built With

- [FastAPI](https://fastapi.tiangolo.com/) — API framework
- [asyncpg](https://magicstack.github.io/asyncpg/) — PostgreSQL async driver
- [Featherless.ai](https://featherless.ai/) — LLM API (Llama 3.1 8B)
- [Meta WhatsApp Business Cloud API](https://developers.facebook.com/docs/whatsapp) — Messaging
- [PostgreSQL](https://www.postgresql.org/) — Database
- [Docker](https://www.docker.com/) — Containerisation
- [Streamlit](https://streamlit.io/) — Dashboard
- [ngrok](https://ngrok.com/) — Local webhook tunneling (dev only)