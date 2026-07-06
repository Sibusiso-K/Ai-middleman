"""
dashboard_api.py — read-only JSON endpoints backing the React dashboard
(ai-middleman/frontend).

All /api/* routes here run analytics/browse queries against the `contacts`
table plus a recent-activity feed off `thread_events`, exposed as JSON for the
web frontend's Home, Contacts, and Analytics pages.
"""

import json
from fastapi import APIRouter, Request, Query
from typing import Optional

router = APIRouter(prefix="/api")


@router.get("/analytics/summary")
async def analytics_summary(request: Request):
    """Return headline KPIs: total contacts, VIP count, avg relationship strength, sector count."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM contacts")
        vip = await conn.fetchval("SELECT COUNT(*) FROM contacts WHERE is_vip = TRUE")
        avg_rel = await conn.fetchval("SELECT ROUND(AVG(relationship_strength)::numeric, 1) FROM contacts")
        sectors = await conn.fetchval(
            "SELECT COUNT(DISTINCT sector) FROM contacts WHERE sector IS NOT NULL AND sector != ''"
        )
    return {
        "total_contacts": total,
        "vip_contacts": vip,
        "avg_relationship_strength": float(avg_rel) if avg_rel is not None else 0,
        "sectors_covered": sectors,
    }


@router.get("/analytics/sectors")
async def analytics_sectors(request: Request):
    """Return contact counts grouped by sector, descending."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sector AS name, COUNT(*) AS value
            FROM contacts
            WHERE sector IS NOT NULL AND sector != ''
            GROUP BY sector
            ORDER BY value DESC
            """
        )
    return [dict(r) for r in rows]


@router.get("/analytics/locations")
async def analytics_locations(request: Request, limit: int = Query(10, le=50)):
    """Return the top `limit` locations by contact count."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT location AS name, COUNT(*) AS value
            FROM contacts
            WHERE location IS NOT NULL AND location != ''
            GROUP BY location
            ORDER BY value DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


@router.get("/analytics/scatter")
async def analytics_scatter(request: Request, limit: int = Query(500, le=2000)):
    """Return a random sample of (relationship_strength, intros_made, sector) points for the scatter plot."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT relationship_strength AS x, intros_made AS y, sector
            FROM contacts
            WHERE relationship_strength IS NOT NULL AND intros_made IS NOT NULL
                AND sector IS NOT NULL AND sector != ''
            ORDER BY random()
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


@router.get("/analytics/deals-by-sector")
async def analytics_deals_by_sector(request: Request):
    """Return average deals-closed per sector, descending."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sector AS name, ROUND(AVG(deals_closed)::numeric, 1) AS value
            FROM contacts
            WHERE sector IS NOT NULL AND sector != '' AND deals_closed IS NOT NULL
            GROUP BY sector
            ORDER BY value DESC
            """
        )
    return [{"name": r["name"], "value": float(r["value"])} for r in rows]


@router.get("/analytics/top-skills")
async def analytics_top_skills(request: Request, limit: int = Query(8, le=30)):
    """Return the top `limit` specialties by contact count."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT specialty AS name, COUNT(*) AS count
            FROM contacts
            WHERE specialty IS NOT NULL AND specialty != ''
            GROUP BY specialty
            ORDER BY count DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


@router.get("/analytics/seniority")
async def analytics_seniority(request: Request):
    """Return contact counts grouped by seniority level, most common first."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT seniority AS name, COUNT(*) AS value
            FROM contacts
            WHERE seniority IS NOT NULL AND seniority != ''
            GROUP BY seniority
            ORDER BY value DESC
            """
        )
    return [dict(r) for r in rows]


@router.get("/analytics/strength-distribution")
async def analytics_strength_distribution(request: Request):
    """Return the count of contacts at each relationship-strength level (1-5)."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT relationship_strength AS level, COUNT(*) AS value
            FROM contacts
            WHERE relationship_strength IS NOT NULL
            GROUP BY relationship_strength
            ORDER BY relationship_strength
            """
        )
    return [{"level": r["level"], "value": r["value"]} for r in rows]


@router.get("/analytics/vip-breakdown")
async def analytics_vip_breakdown(request: Request):
    """Return the VIP vs standard contact split for a donut chart."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        vip = await conn.fetchval("SELECT COUNT(*) FROM contacts WHERE is_vip = TRUE")
        standard = await conn.fetchval("SELECT COUNT(*) FROM contacts WHERE is_vip = FALSE OR is_vip IS NULL")
    return [
        {"name": "VIP", "value": vip},
        {"name": "Standard", "value": standard},
    ]


# --- Conversation analytics: computed from the live thread_events log, not the
# static contacts table. These reflect what Sam actually asked for and how Alex
# acted on the AI's drafts. -------------------------------------------------

# Reusable CTE: every contact suggested in a draft, one row per (draft, contact),
# safely extracting the numeric contact_id from the draft's JSONB matches array.
_SUGGESTED_CONTACTS_CTE = """
    WITH suggested AS (
        SELECT (m->>'contact_id')::int AS cid
        FROM thread_events te
        CROSS JOIN LATERAL jsonb_array_elements(te.payload->'matches') AS m
        WHERE te.event_type = 'draft_suggested'
          AND jsonb_typeof(te.payload->'matches') = 'array'
          AND (m->>'contact_id') ~ '^[0-9]+$'
    )
"""


@router.get("/analytics/conversation-summary")
async def conversation_summary(request: Request):
    """Headline conversation KPIs from thread_events: messages from Sam, drafts
    the AI generated, and how Alex resolved them (the approval rate)."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT event_type, COUNT(*) AS n FROM thread_events GROUP BY event_type"
        )
    counts = {r["event_type"]: r["n"] for r in rows}
    suggested = counts.get("draft_suggested", 0)
    sent = counts.get("draft_sent", 0)
    edited = counts.get("draft_edited", 0)
    skipped = counts.get("draft_skipped", 0)
    resolved = sent + edited + skipped
    return {
        "messages_from_sam": counts.get("friend_message", 0),
        "drafts_generated": suggested,
        "drafts_sent": sent,
        "drafts_edited": edited,
        "drafts_skipped": skipped,
        "alex_replies": counts.get("alex_reply", 0),
        "approval_rate": round(sent / resolved, 3) if resolved else 0.0,
    }


@router.get("/analytics/approval-funnel")
async def approval_funnel(request: Request):
    """How Alex acted on the AI's drafts — the Send / Edit / Skip breakdown
    (plus any still pending), for a funnel or donut chart."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT event_type, COUNT(*) AS n FROM thread_events
            WHERE event_type IN ('draft_suggested','draft_sent','draft_edited','draft_skipped')
            GROUP BY event_type
            """
        )
    c = {r["event_type"]: r["n"] for r in rows}
    suggested = c.get("draft_suggested", 0)
    sent, edited, skipped = c.get("draft_sent", 0), c.get("draft_edited", 0), c.get("draft_skipped", 0)
    pending = max(0, suggested - (sent + edited + skipped))
    return [
        {"name": "Sent", "value": sent},
        {"name": "Edited", "value": edited},
        {"name": "Skipped", "value": skipped},
        {"name": "Pending", "value": pending},
    ]


@router.get("/analytics/requested-sectors")
async def requested_sectors(request: Request):
    """Which sectors Sam's requests actually pull in — the sector of every
    contact the AI suggested, tallied. Reflects demand, not just supply."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            _SUGGESTED_CONTACTS_CTE + """
            SELECT co.sector AS name, COUNT(*) AS value
            FROM suggested s JOIN contacts co ON co.id = s.cid
            WHERE co.sector IS NOT NULL AND co.sector != ''
            GROUP BY co.sector ORDER BY value DESC
            """
        )
    return [dict(r) for r in rows]


@router.get("/analytics/requested-services")
async def requested_services(request: Request, limit: int = Query(8, le=30)):
    """The top specialties/services Sam's requests surface — the specialty of
    every suggested contact, tallied."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            _SUGGESTED_CONTACTS_CTE + """
            SELECT co.specialty AS name, COUNT(*) AS value
            FROM suggested s JOIN contacts co ON co.id = s.cid
            WHERE co.specialty IS NOT NULL AND co.specialty != ''
            GROUP BY co.specialty ORDER BY value DESC LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


@router.get("/analytics/top-requested-contacts")
async def top_requested_contacts(request: Request, limit: int = Query(8, le=30)):
    """The people the AI recommends most often across all conversations."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            _SUGGESTED_CONTACTS_CTE + """
            SELECT co.full_name AS name, co.title, co.company, COUNT(*) AS value
            FROM suggested s JOIN contacts co ON co.id = s.cid
            GROUP BY co.id, co.full_name, co.title, co.company
            ORDER BY value DESC LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


@router.get("/analytics/requested-locations")
async def requested_locations(request: Request, limit: int = Query(10, le=50)):
    """The top locations Sam's requests pull in — the location of every
    contact the AI suggested, tallied. The geographic demand signal."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            _SUGGESTED_CONTACTS_CTE + """
            SELECT co.location AS name, COUNT(*) AS value
            FROM suggested s JOIN contacts co ON co.id = s.cid
            WHERE co.location IS NOT NULL AND co.location != ''
            GROUP BY co.location ORDER BY value DESC LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


@router.get("/analytics/channel-mix")
async def channel_mix(request: Request):
    """How Sam's messages arrive — typed, voice note, or image. Media messages
    are stored text-prefixed (🎙️ / 🖼️) by the transcription pipeline, so the
    channel is recoverable from the friend_message payload."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT CASE
                WHEN payload->>'text' LIKE '🎙️%' THEN 'Voice note'
                WHEN payload->>'text' LIKE '🖼️%' THEN 'Image'
                ELSE 'Typed' END AS name,
                COUNT(*) AS value
            FROM thread_events
            WHERE event_type = 'friend_message'
            GROUP BY name ORDER BY value DESC
            """
        )
    return [dict(r) for r in rows]


@router.get("/analytics/confidence-calibration")
async def confidence_calibration(request: Request):
    """Is the ranker's confidence calibrated against Alex's decision? For each
    draft, take the top match's confidence and whether Alex ultimately Sent it,
    bucketed by confidence. A rising Send-rate with confidence = calibrated.

    Each draft is paired with the first Send/Edit/Skip that follows it and
    precedes the next draft — a temporal join, since resolution events don't
    carry the draft's id."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            r"""
            WITH drafts AS (
                SELECT te.id, te.created_at,
                    (SELECT MAX((m->>'confidence')::float)
                     FROM jsonb_array_elements(te.payload->'matches') m
                     WHERE (m->>'confidence') ~ '^[0-9.]+$') AS conf,
                    LEAD(te.created_at) OVER (ORDER BY te.created_at) AS next_at
                FROM thread_events te
                WHERE te.event_type = 'draft_suggested'
                  AND jsonb_typeof(te.payload->'matches') = 'array'
            ),
            resolved AS (
                SELECT d.conf,
                    (SELECT r.event_type FROM thread_events r
                     WHERE r.event_type IN ('draft_sent','draft_edited','draft_skipped')
                       AND r.created_at > d.created_at
                       AND (d.next_at IS NULL OR r.created_at < d.next_at)
                     ORDER BY r.created_at LIMIT 1) AS outcome
                FROM drafts d WHERE d.conf IS NOT NULL
            )
            SELECT CASE
                     WHEN conf < 0.6 THEN '<0.6'
                     WHEN conf < 0.7 THEN '0.6-0.7'
                     WHEN conf < 0.8 THEN '0.7-0.8'
                     WHEN conf < 0.9 THEN '0.8-0.9'
                     ELSE '0.9-1.0' END AS bucket,
                   COUNT(*) FILTER (WHERE outcome IS NOT NULL) AS resolved,
                   COUNT(*) FILTER (WHERE outcome = 'draft_sent') AS sent
            FROM resolved GROUP BY bucket ORDER BY bucket
            """
        )
    out = []
    for r in rows:
        resolved = r["resolved"] or 0
        out.append({
            "bucket": r["bucket"],
            "resolved": resolved,
            "sent": r["sent"] or 0,
            "send_rate": round((r["sent"] or 0) / resolved, 3) if resolved else 0.0,
        })
    return out


@router.get("/filters/options")
async def filter_options(request: Request):
    """Return the distinct sector/location/seniority values for the Contacts page filters."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        sectors = await conn.fetch(
            "SELECT DISTINCT sector FROM contacts WHERE sector IS NOT NULL AND sector != '' ORDER BY sector"
        )
        locations = await conn.fetch(
            "SELECT DISTINCT location FROM contacts WHERE location IS NOT NULL AND location != '' ORDER BY location"
        )
        seniorities = await conn.fetch(
            "SELECT DISTINCT seniority FROM contacts WHERE seniority IS NOT NULL AND seniority != '' ORDER BY seniority"
        )
    return {
        "sectors": [r["sector"] for r in sectors],
        "locations": [r["location"] for r in locations],
        "seniorities": [r["seniority"] for r in seniorities],
    }


@router.get("/contacts")
async def list_contacts(
    request: Request,
    search: Optional[str] = None,
    sector: Optional[str] = None,
    location: Optional[str] = None,
    seniority: Optional[str] = None,
    vip: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
):
    """Return a filtered, paginated page of contacts plus the total match count."""
    pool = request.app.state.db_pool
    conditions = []
    args: list = []

    def add(cond: str, value) -> None:
        args.append(value)
        conditions.append(cond.format(n=len(args)))

    if search:
        add("(full_name ILIKE '%' || ${n} || '%' OR company ILIKE '%' || ${n} || '%' OR title ILIKE '%' || ${n} || '%')", search)
    if sector:
        add("sector = ${n}", sector)
    if location:
        add("location = ${n}", location)
    if seniority:
        add("seniority = ${n}", seniority)
    if vip is not None:
        add("is_vip = ${n}", vip)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * page_size

    async with pool.acquire() as conn:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM contacts {where}", *args)
        rows = await conn.fetch(
            f"""
            SELECT id, full_name, title, company, sector, location, seniority,
                   relationship_strength, is_vip, intros_made
            FROM contacts
            {where}
            ORDER BY full_name, id
            LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}
            """,
            *args,
            page_size,
            offset,
        )

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/contacts/{contact_id}")
async def get_contact(request: Request, contact_id: int):
    """Return a single contact's full record plus its most recent match-history rows."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        contact = await conn.fetchrow("SELECT * FROM contacts WHERE id = $1", contact_id)
        if not contact:
            return {"error": "not found"}
        history = await conn.fetch(
            """
            SELECT mh.confidence, mh.reasoning, mh.created_at, m.message_text
            FROM match_history mh
            JOIN messages m ON m.id = mh.message_id
            WHERE mh.contact_id = $1
            ORDER BY mh.created_at DESC
            LIMIT 5
            """,
            contact_id,
        )
    return {"contact": dict(contact), "recent_matches": [dict(r) for r in history]}


@router.get("/activity")
async def recent_activity(request: Request, limit: int = Query(10, le=50)):
    """Recent cross-thread events for the Home page 'Today' feed."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT te.event_type, te.payload, te.created_at, t.sender_number
            FROM thread_events te
            JOIN threads t ON t.id = te.thread_id
            ORDER BY te.created_at DESC
            LIMIT $1
            """,
            limit,
        )
    events = [dict(r) for r in rows]
    for e in events:
        if isinstance(e["payload"], str):
            e["payload"] = json.loads(e["payload"])
    return events
