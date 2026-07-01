# Architecture — AI Middleman

## System Overview

AI Middleman is a two-stage AI contact matching system that operates over WhatsApp. It receives natural language queries and returns ranked professional contacts with confidence scores and reasoning.

## Two-Stage Pipeline

### Why Two Stages?

Sending 50,000 contacts directly to an LLM would:
- Exceed context window limits (50k contacts ≈ 5M+ tokens)
- Cost $50-200 per query with GPT-4
- Take minutes per response

The two-stage approach solves this:

**Stage 1 (free, <100ms):** Keyword filter reduces 50,000 → 30-50 candidates
**Stage 2 (free tier, 2-3s):** LLM ranks 30-50 → top 5 with reasoning

Total cost: $0. Total time: 2-3 seconds.

### Stage 1: Keyword Filter

```python
# Extracts tokens from query
tokens = ["credit", "finance", "specialist", "london"]

# Searches 9 fields with location awareness
# Location-matched contacts float to top
# Returns 30-50 ordered candidates
```

Fields searched: `full_name`, `title`, `company`, `sector`, `specialty`, `expertise_tags`, `can_help_with`, `looking_for`, `comment`

Location awareness: If query contains a city/country name, contacts in that location are boosted to the top of the candidate list before LLM evaluation.

### Stage 2: LLM Agent

Receives 30-50 candidates and applies strict scoring rules:

| Priority | Factor | Impact |
|---|---|---|
| 1 | Location match | Wrong location caps score at 0.6 |
| 2 | Role/skill match | Direct match required for >0.8 |
| 3 | Seniority | Partner/MD > Analyst/Associate |
| 4 | Relationship strength | 4-5 preferred over 1-2 |
| 5 | VIP status | Tiebreaker only |

## Database Schema

```sql
contacts          -- 50,000 professional contacts (23 columns)
messages          -- Inbound WhatsApp message log
match_history     -- Match results per message with feedback
```

## Request Flow

```
1. User sends WhatsApp message
2. Meta Cloud API receives message
3. Meta POSTs webhook event to Callback URL
4. FastAPI webhook receiver validates and parses
5. Message saved to messages table
6. MatchingEngine.match(query) called
7. KeywordFilter returns 30-50 candidates
8. LLMAgent evaluates and ranks candidates
9. ResponseFormatter converts JSON to WhatsApp text
10. WhatsAppClient sends reply via Graph API
11. User receives ranked contacts on WhatsApp
```

## Technology Rationale

**asyncpg over SQLAlchemy:** Pure async driver, no ORM overhead, better performance for concurrent webhook handling.

**Raw HTTP over LangChain:** Fewer dependencies, easier debugging, full control over prompt structure and API calls.

**Featherless.ai over OpenAI:** Free tier with Llama 3.1 8B (128k context window) handles 30-50 candidates in a single prompt at zero cost.

**No pgvector:** With 50,000 contacts, keyword filtering is fast enough and avoids embedding generation, storage, and update complexity.