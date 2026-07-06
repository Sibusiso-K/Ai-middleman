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
