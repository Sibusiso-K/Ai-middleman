"""
dashboard/app.py — Streamlit dashboard for AI Middleman.

Pages:
  0. Live Threads — Alex's control surface: live conversation threads with
     inline draft suggestions, SEND/EDIT/SKIP, and per-thread autonomy toggle
  1. Database Overview — metrics, charts, VIP table
  2. Match Tester — natural language query testing with styled results
  3. Contact Browser — filtered search with expandable detail
  4. Analytics — scatter plots, bar charts, top-10 tables

Connects directly to PostgreSQL via asyncpg and the FastAPI match endpoint.
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import asyncpg
import requests
import os
import sys
import time
import json
from datetime import datetime
from dotenv import load_dotenv

# Load .env from parent directory
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:yourpassword@localhost:5432/aimiddleman")
API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="AI Middleman",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Database helpers ──────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_db_pool():
    """Create a connection pool (cached)."""
    return None  # We'll create connections on demand


async def _fetch(query: str, *args):
    """Execute a query and return rows as list of dicts."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


def run_query(query: str, *args):
    """Sync wrapper for async DB queries."""
    import asyncio
    return asyncio.run(_fetch(query, *args))


async def _execute(query: str, *args):
    """Execute a query that modifies data (INSERT/UPDATE/DELETE)."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        result = await conn.execute(query, *args)
        return result
    finally:
        await conn.close()


def run_execute(query: str, *args):
    """Sync wrapper for async DB mutations."""
    import asyncio
    return asyncio.run(_execute(query, *args))


# ── Sidebar ───────────────────────────────────────────────────────

st.sidebar.title("🤝 AI Middleman")
st.sidebar.caption("Contact Intelligence Platform")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    [
        "🧑 Friend — Sam",
        "💬 Live Threads",
        "📊 Database Overview",
        "🔍 Match Tester",
        "📋 Contact Browser",
        "📈 Analytics",
    ],
)

st.sidebar.markdown("---")
st.sidebar.markdown("**System Status**")

# Check API health
try:
    r = requests.get(f"{API_URL}/health", timeout=2)
    if r.status_code == 200:
        st.sidebar.success("✅ API Online")
    else:
        st.sidebar.error(f"❌ API Error ({r.status_code})")
except Exception:
    st.sidebar.error("❌ API Offline")

# Check database
try:
    run_query("SELECT 1")
    st.sidebar.success("✅ Database Online")
except Exception as e:
    st.sidebar.error(f"❌ Database Offline")

st.sidebar.markdown("---")
st.sidebar.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")
st.sidebar.markdown("---")
st.sidebar.caption("AI Middleman Dashboard v1.0")


# ═══════════════════════════════════════════════════════════════════
# PAGE 0 — Friend (Sam): role-play the friend, two-way WhatsApp chat
# ═══════════════════════════════════════════════════════════════════

if page == "🧑 Friend — Sam":
    st.title("🧑 Friend — Sam")
    st.caption("Send messages as Sam. They go to Alex's real WhatsApp; his replies come back here.")

    st.info(
        "ℹ️ Messages send from the Cloud API number (27650746242) to Alex (27736013348). "
        "Alex must have messaged that number within the last 24h for WhatsApp to accept free-form sends."
    )

    col_ar, col_rf = st.columns([1, 1])
    auto_refresh = col_ar.checkbox("Auto-refresh every 3s", value=False, key="friend_autorefresh")
    if col_rf.button("🔄 Refresh now", key="friend_refresh"):
        st.rerun()

    # ── Load the conversation ──
    events = []
    try:
        resp = requests.get(f"{API_URL}/friend/thread", timeout=10)
        if resp.status_code == 200:
            events = resp.json().get("events", [])
        else:
            st.error(f"Could not load thread: {resp.status_code}")
    except Exception as e:
        st.error(f"Could not reach API: {e}")

    # ── Render transcript ──
    for e in events:
        etype = e.get("event_type")
        payload = e.get("payload", {})
        if isinstance(payload, str):
            payload = json.loads(payload)

        if etype == "friend_message":
            with st.chat_message("user"):
                st.markdown(f"**Sam:** {payload.get('text', '')}")
        elif etype == "alex_reply":
            with st.chat_message("assistant"):
                st.markdown(f"**Alex:** {payload.get('text', '')}")
        elif etype == "draft_sent":
            with st.chat_message("assistant"):
                st.markdown(f"**Alex:** {payload.get('final_text', '')}")
        elif etype == "draft_skipped":
            st.caption("— Alex skipped a suggested reply (nothing sent) —")
        elif etype == "draft_suggested":
            st.caption("⏳ Alex has a suggested reply pending on his WhatsApp…")

    if not events:
        st.caption("No messages yet. Say hi as Sam below 👇")

    # ── Input box ──
    prompt = st.chat_input("Message as Sam…")
    if prompt:
        try:
            r = requests.post(f"{API_URL}/friend/send", json={"text": prompt}, timeout=90)
            if r.status_code == 200:
                data = r.json()
                if not data.get("relayed_to_alex"):
                    st.warning("Message logged, but WhatsApp relay to Alex failed (check the 24h window / token).")
            else:
                st.error(f"Send failed: {r.status_code} {r.text}")
        except Exception as e:
            st.error(f"Send failed: {e}")
        st.rerun()

    if auto_refresh:
        # Non-blocking: reload the page in 3s instead of sleeping the script
        # thread (which would leave Streamlit stuck in a "Running…" state).
        components.html(
            "<script>setTimeout(function(){ window.parent.location.reload(); }, 3000);</script>",
            height=0,
        )


# ═══════════════════════════════════════════════════════════════════
# PAGE 0b — Live Threads (read-only monitoring; approval happens on WhatsApp)
# ═══════════════════════════════════════════════════════════════════

elif page == "💬 Live Threads":
    st.title("💬 Live Threads")
    st.caption("Read-only monitoring of every thread. Draft approval happens on Alex's WhatsApp, not here.")

    auto_refresh = st.checkbox("Auto-refresh every 3s", value=False)

    threads = run_query("""
        SELECT t.id, t.sender_number, t.autonomy_mode, t.updated_at,
               (SELECT COUNT(*) FROM thread_events e
                WHERE e.thread_id = t.id AND e.event_type = 'draft_suggested'
                  AND NOT EXISTS (
                      SELECT 1 FROM thread_events e2
                      WHERE e2.thread_id = t.id
                        AND e2.event_type IN ('draft_sent', 'draft_edited', 'draft_skipped')
                        AND e2.created_at > e.created_at
                  )) AS pending_count
        FROM threads t
        ORDER BY t.updated_at DESC
    """)

    if not threads:
        st.info("No conversations yet — once a message flows through the system, threads show up here.")
    else:
        pending_total = sum(t["pending_count"] for t in threads)
        st.markdown(f"**{len(threads)}** thread(s) · **{pending_total}** draft(s) awaiting Alex on WhatsApp")
        st.markdown("---")

        for t in threads:
            pending_badge = f" 🟡 {t['pending_count']} pending" if t["pending_count"] else ""
            with st.expander(f"📱 {t['sender_number']}{pending_badge}", expanded=t["pending_count"] > 0):
                st.caption(f"Last activity: {t['updated_at'].strftime('%Y-%m-%d %H:%M') if t['updated_at'] else 'N/A'}")

                events = run_query("""
                    SELECT id, event_type, payload, created_at
                    FROM thread_events
                    WHERE thread_id = $1
                    ORDER BY created_at ASC
                """, t["id"])

                for e in events:
                    payload = e["payload"] if isinstance(e["payload"], dict) else json.loads(e["payload"])
                    ts = e["created_at"].strftime("%H:%M") if e["created_at"] else ""
                    etype = e["event_type"]

                    if etype == "friend_message":
                        st.markdown(f"**{ts} · 🧑 Sam:** {payload.get('text', '')}")

                    elif etype == "alex_reply":
                        st.markdown(f"**{ts} · 👤 Alex:** {payload.get('text', '')}")

                    elif etype == "draft_suggested":
                        matches = payload.get("matches", [])
                        with st.container(border=True):
                            st.markdown(f"**{ts} · 🤖 Draft suggested (on Alex's WhatsApp)**")
                            if matches:
                                for i, m in enumerate(matches[:5], 1):
                                    conf = int(m.get("confidence", 0) * 100)
                                    st.caption(f"{i}. {m.get('name', 'Unknown')} — {m.get('title', '')} at {m.get('company', '')} ({conf}%)")
                            else:
                                st.caption("No strong matches found.")
                            st.caption(f"Draft: _{payload.get('draft_reply', '')}_")

                    elif etype in ("draft_sent", "draft_edited", "draft_skipped"):
                        label = {"draft_sent": "✅ Sent", "draft_edited": "✏️ Sent (edited)", "draft_skipped": "❌ Skipped"}[etype]
                        final_text = payload.get("final_text", "")
                        st.caption(f"{ts} · {label}" + (f": {final_text}" if final_text else ""))

    if auto_refresh:
        components.html(
            "<script>setTimeout(function(){ window.parent.location.reload(); }, 3000);</script>",
            height=0,
        )


# ═══════════════════════════════════════════════════════════════════
# PAGE 1 — Database Overview
# ═══════════════════════════════════════════════════════════════════

elif page == "📊 Database Overview":
    st.title("🤝 AI Middleman — Contact Intelligence Platform")
    st.caption("Automating business connections through intelligent AI matching")
    st.markdown("---")

    # ── Metric cards ──
    total = run_query("SELECT COUNT(*) AS cnt FROM contacts")[0]["cnt"]
    vip_count = run_query("SELECT COUNT(*) AS cnt FROM contacts WHERE is_vip = TRUE")[0]["cnt"]
    avg_rel = run_query("SELECT ROUND(AVG(relationship_strength)::numeric, 1) AS avg FROM contacts")[0]["avg"]
    sector_count = run_query("SELECT COUNT(DISTINCT sector) AS cnt FROM contacts WHERE sector IS NOT NULL AND sector != ''")[0]["cnt"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Contacts", f"{total:,}")
    col2.metric("VIP Contacts", f"{vip_count:,}")
    col3.metric("Avg Relationship Strength", f"{avg_rel} / 5")
    col4.metric("Sectors Covered", str(sector_count))

    st.markdown("---")

    # ── Charts row 1 ──
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Contacts by Sector")
        sector_data = run_query("""
            SELECT sector, COUNT(*) AS cnt
            FROM contacts
            WHERE sector IS NOT NULL AND sector != ''
            GROUP BY sector
            ORDER BY cnt DESC
        """)
        if sector_data:
            df_sector = pd.DataFrame(sector_data)
            # Professional colour palette
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                      '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
            fig = px.pie(df_sector, names="sector", values="cnt", hole=0.4,
                         color_discrete_sequence=colors)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(height=420, margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No sector data available.")

    with col_right:
        st.subheader("Top 10 Locations")
        loc_data = run_query("""
            SELECT location, COUNT(*) AS cnt
            FROM contacts
            WHERE location IS NOT NULL AND location != ''
            GROUP BY location
            ORDER BY cnt DESC
            LIMIT 10
        """)
        if loc_data:
            df_loc = pd.DataFrame(loc_data)
            fig = px.bar(df_loc, y="location", x="cnt", orientation='h',
                         color="cnt", color_continuous_scale="Blues",
                         text_auto=True)
            fig.update_layout(height=420, yaxis_title="", xaxis_title="Contacts",
                              margin=dict(t=10, b=10))
            fig.update_coloraxes(showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No location data available.")

    # ── Charts row 2 ──
    col_left2, col_right2 = st.columns(2)

    with col_left2:
        st.subheader("Contacts by Seniority")
        sen_data = run_query("""
            SELECT seniority, COUNT(*) AS cnt
            FROM contacts
            WHERE seniority IS NOT NULL AND seniority != ''
            GROUP BY seniority
            ORDER BY cnt DESC
        """)
        if sen_data:
            df_sen = pd.DataFrame(sen_data)
            fig = px.bar(df_sen, x="seniority", y="cnt", color="cnt",
                         color_continuous_scale="Greens", text_auto=True)
            fig.update_layout(height=400, xaxis_title="", yaxis_title="Contacts",
                              margin=dict(t=10, b=10))
            fig.update_coloraxes(showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No seniority data available.")

    with col_right2:
        st.subheader("Relationship Strength Distribution")
        rel_data = run_query("""
            SELECT relationship_strength, COUNT(*) AS cnt
            FROM contacts
            WHERE relationship_strength IS NOT NULL
            GROUP BY relationship_strength
            ORDER BY relationship_strength
        """)
        if rel_data:
            df_rel = pd.DataFrame(rel_data)
            fig = px.bar(df_rel, x="relationship_strength", y="cnt", color="cnt",
                         color_continuous_scale="Oranges", text_auto=True)
            fig.update_layout(height=400, xaxis_title="Strength (1-5)", yaxis_title="Contacts",
                              margin=dict(t=10, b=10))
            fig.update_coloraxes(showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No relationship data available.")

    # ── VIP table ──
    st.markdown("---")
    st.subheader("🏆 Top 20 VIP Contacts")
    vip_data = run_query("""
        SELECT full_name, title, company, sector, relationship_strength
        FROM contacts
        WHERE is_vip = TRUE
        ORDER BY relationship_strength DESC
        LIMIT 20
    """)
    if vip_data:
        df_vip = pd.DataFrame(vip_data)
        df_vip.columns = ["Name", "Title", "Company", "Sector", "Relationship Strength"]
        st.dataframe(df_vip, use_container_width=True, hide_index=True)
    else:
        st.info("No VIP contacts found.")


# ═══════════════════════════════════════════════════════════════════
# PAGE 2 — Match Tester
# ═══════════════════════════════════════════════════════════════════

elif page == "🔍 Match Tester":
    st.title("🔍 AI Contact Matching")
    st.caption("Describe who you need and let AI find the best matches in seconds.")

    # Centered input area
    col_center, col_buffer = st.columns([3, 1])
    with col_center:
        query = st.text_area(
            "Describe who you are looking for...",
            placeholder="e.g. I need a VP of Leveraged Finance in London who specialises in unitranche deals...",
            height=80,
            label_visibility="collapsed",
        )

    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        search_clicked = st.button("🔍 Find Matches", type="primary", use_container_width=True)

    if search_clicked:
        if not query.strip():
            st.warning("Please enter a search query.")
        else:
            with st.spinner("Running AI matching pipeline..."):
                start_time = time.time()
                try:
                    resp = requests.post(
                        f"{API_URL}/match",
                        json={"query": query.strip()},
                        timeout=90,
                    )
                    elapsed = time.time() - start_time

                    if resp.status_code == 200:
                        data = resp.json()
                        match_quality = data.get("match_quality", "none")
                        matches = data.get("matches", [])
                        formatted = data.get("formatted_response", "")
                        clarification = data.get("clarification_question", "")
                        candidates_count = data.get("candidates_count", "?")

                        # Pipeline stats expander
                        with st.expander("📊 Pipeline Stats", expanded=False):
                            cols_stats = st.columns(4)
                            cols_stats[0].metric("Keyword Candidates", candidates_count)
                            cols_stats[1].metric("LLM Matches", len(matches))
                            cols_stats[2].metric("Match Quality", match_quality.upper())
                            cols_stats[3].metric("Time Taken", f"{elapsed:.1f}s")

                        if match_quality == "none":
                            st.warning(f"⚠️ {clarification or 'No matches found. Try a different query.'}")
                        else:
                            quality_label = "Strong Matches" if match_quality == "good" else "Partial Matches"
                            quality_icon = "✅" if match_quality == "good" else "⚠️"
                            st.markdown(f"### {quality_icon} {quality_label} ({len(matches)} found)")

                            for m in matches:
                                conf = m.get("confidence", 0)
                                conf_pct = int(conf * 100)

                                # Confidence bar colour
                                if conf_pct >= 70:
                                    bar_color = "normal"
                                    emoji = "🟢"
                                elif conf_pct >= 40:
                                    bar_color = "normal"
                                    emoji = "🟡"
                                else:
                                    bar_color = "normal"
                                    emoji = "🔴"

                                with st.container(border=True):
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        contact_id = m.get('contact_id', 'N/A')
                                        vip_badge = " ⭐ VIP" if m.get('is_vip') else ""
                                        st.markdown(f"**Contact #{contact_id}**{vip_badge}")
                                        st.markdown(f"*{m.get('title', 'N/A')}* at **{m.get('company', 'N/A')}**")
                                        st.caption(f"📍 {m.get('location', 'N/A')}  |  🏢 {m.get('sector', 'N/A')}  |  🎯 {m.get('seniority', 'N/A')}")

                                    with col2:
                                        st.markdown(f"### {emoji} {conf_pct}%")
                                        st.progress(conf, text=f"{conf_pct}% match")

                                    # Reasoning in a light box
                                    reasoning = m.get('reasoning', 'No reasoning provided.')
                                    st.info(f"💬 {reasoning}")

                            # WhatsApp preview
                            if formatted:
                                st.markdown("---")
                                st.subheader("📱 WhatsApp Preview")
                                st.code(formatted, language="text")

                    else:
                        st.error(f"API returned status {resp.status_code}: {resp.text}")
                except requests.exceptions.ConnectionError:
                    st.error("⚠️ Cannot connect to the API. Make sure the FastAPI server is running on port 8000.")
                except requests.exceptions.Timeout:
                    st.error("⚠️ Request timed out. The LLM may be taking too long to respond.")
                except Exception as e:
                    st.error(f"⚠️ Error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# PAGE 3 — Contact Browser
# ═══════════════════════════════════════════════════════════════════

elif page == "📋 Contact Browser":
    st.title("📋 Contact Browser")
    st.caption("Browse and search the full contact database.")

    # ── Sidebar filters ──
    st.sidebar.markdown("### 🔎 Filters")

    # Get distinct values for dropdowns
    sectors = run_query("SELECT DISTINCT sector FROM contacts WHERE sector IS NOT NULL AND sector != '' ORDER BY sector")
    sector_options = ["All"] + [r["sector"] for r in sectors]

    seniorities = run_query("SELECT DISTINCT seniority FROM contacts WHERE seniority IS NOT NULL AND seniority != '' ORDER BY seniority")
    seniority_options = ["All"] + [r["seniority"] for r in seniorities]

    selected_sector = st.sidebar.selectbox("Sector", sector_options)
    selected_seniority = st.sidebar.selectbox("Seniority", seniority_options)
    vip_only = st.sidebar.toggle("VIP only", value=False)
    rel_min, rel_max = st.sidebar.slider(
        "Relationship Strength", 1, 5, (1, 5)
    )
    text_search = st.sidebar.text_input("🔍 Free text search", placeholder="Name, company, title...")

    # ── Build query ──
    conditions = []
    params = []

    if selected_sector != "All":
        params.append(selected_sector)
        conditions.append(f"sector = ${len(params)}")
    if selected_seniority != "All":
        params.append(selected_seniority)
        conditions.append(f"seniority = ${len(params)}")
    if vip_only:
        conditions.append("is_vip = TRUE")
    params.append(rel_min)
    conditions.append(f"relationship_strength >= ${len(params)}")
    params.append(rel_max)
    conditions.append(f"relationship_strength <= ${len(params)}")
    if text_search.strip():
        params.append(f"%{text_search.strip()}%")
        conditions.append(f"""
            (full_name ILIKE ${len(params)}
             OR company ILIKE ${len(params)}
             OR title ILIKE ${len(params)}
             OR expertise_tags ILIKE ${len(params)})
        """)

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    query_sql = f"""
        SELECT id, full_name, title, company, sector, location, seniority,
               relationship_strength, is_vip, preferred_contact_channel,
               comment, expertise_tags, can_help_with, looking_for
        FROM contacts
        WHERE {where_clause}
        ORDER BY relationship_strength DESC, full_name ASC
    """

    results = run_query(query_sql, *params)
    st.markdown(f"**{len(results)}** contact(s) found")

    if results:
        df = pd.DataFrame(results)

        # Display columns
        display_cols = {
            "full_name": "Name",
            "title": "Title",
            "company": "Company",
            "sector": "Sector",
            "location": "Location",
            "seniority": "Seniority",
            "relationship_strength": "Rel. Strength",
            "is_vip": "VIP",
        }
        df_display = df[list(display_cols.keys())].copy()
        df_display.columns = list(display_cols.values())
        df_display["VIP"] = df_display["VIP"].apply(lambda x: "⭐" if x else "")

        # Pagination
        page_size = 25
        total_pages = max(1, (len(df_display) + page_size - 1) // page_size)
        page_num = st.number_input("Page", min_value=1, max_value=total_pages, value=1, label_visibility="collapsed")
        start = (page_num - 1) * page_size
        end = start + page_size

        st.dataframe(df_display.iloc[start:end], use_container_width=True, hide_index=True)
        st.caption(f"Page {page_num} of {total_pages}")

        # ── Expand row detail ──
        st.markdown("---")
        st.subheader("🔍 Contact Detail")
        selected_name = st.selectbox("Select a contact to view details:", df["full_name"].tolist())
        if selected_name:
            contact = df[df["full_name"] == selected_name].iloc[0]
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**Name:** {contact['full_name']}")
                st.markdown(f"**Title:** {contact['title']}")
                st.markdown(f"**Company:** {contact['company']}")
                st.markdown(f"**Sector:** {contact['sector']}")
                st.markdown(f"**Location:** {contact['location']}")
                st.markdown(f"**Seniority:** {contact['seniority']}")
            with col_b:
                st.markdown(f"**Relationship Strength:** {'⭐' * contact['relationship_strength']}")
                st.markdown(f"**VIP:** {'Yes' if contact['is_vip'] else 'No'}")
                st.markdown(f"**Channel:** {contact.get('preferred_contact_channel', 'N/A')}")
                st.markdown(f"**Expertise:** {contact.get('expertise_tags', 'N/A')}")
                st.markdown(f"**Can Help With:** {contact.get('can_help_with', 'N/A')}")
                st.markdown(f"**Looking For:** {contact.get('looking_for', 'N/A')}")
            if contact.get("comment"):
                st.markdown(f"**Comment:** {contact['comment']}")
    else:
        st.info("No contacts match the current filters.")


# ═══════════════════════════════════════════════════════════════════
# PAGE 4 — Analytics
# ═══════════════════════════════════════════════════════════════════

elif page == "📈 Analytics":
    st.title("📈 Analytics")
    st.caption("Deeper insights into the contact network.")

    # ── Scatter: relationship_strength vs intros_made ──
    st.subheader("Relationship Strength vs. Intros Made")
    scatter_data = run_query("""
        SELECT full_name, relationship_strength, intros_made, sector
        FROM contacts
        WHERE intros_made IS NOT NULL AND relationship_strength IS NOT NULL
    """)
    if scatter_data:
        df_scatter = pd.DataFrame(scatter_data)
        fig = px.scatter(
            df_scatter,
            x="relationship_strength",
            y="intros_made",
            color="sector",
            hover_name="full_name",
            size_max=10,
            title="Relationship Strength vs Intros Made (coloured by sector)",
        )
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data for scatter plot.")

    # ── Bar: avg deals_closed by sector ──
    st.subheader("Average Deals Closed by Sector")
    deals_data = run_query("""
        SELECT sector, ROUND(AVG(deals_closed)::numeric, 1) AS avg_deals
        FROM contacts
        WHERE deals_closed IS NOT NULL AND sector IS NOT NULL AND sector != ''
        GROUP BY sector
        ORDER BY avg_deals DESC
    """)
    if deals_data:
        df_deals = pd.DataFrame(deals_data)
        fig = px.bar(df_deals, x="sector", y="avg_deals", color="avg_deals",
                     color_continuous_scale="Blues", text_auto=True)
        fig.update_layout(height=400, xaxis_title="", yaxis_title="Avg Deals Closed")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No deals data available.")

    # ── Bar: top 10 companies by contact count ──
    st.subheader("Top 10 Companies by Contact Count")
    comp_data = run_query("""
        SELECT company, COUNT(*) AS cnt
        FROM contacts
        WHERE company IS NOT NULL AND company != ''
        GROUP BY company
        ORDER BY cnt DESC
        LIMIT 10
    """)
    if comp_data:
        df_comp = pd.DataFrame(comp_data)
        fig = px.bar(df_comp, x="company", y="cnt", color="cnt",
                     color_continuous_scale="Greens", text_auto=True)
        fig.update_layout(height=400, xaxis_title="", yaxis_title="Contacts")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No company data available.")

    # ── Table: top 10 by intros_made ──
    st.subheader("🏆 Top 10 Contacts by Intros Made")
    intros_data = run_query("""
        SELECT full_name, title, company, sector, intros_made, deals_closed
        FROM contacts
        WHERE intros_made IS NOT NULL
        ORDER BY intros_made DESC
        LIMIT 10
    """)
    if intros_data:
        df_intros = pd.DataFrame(intros_data)
        df_intros.columns = ["Name", "Title", "Company", "Sector", "Intros Made", "Deals Closed"]
        st.dataframe(df_intros, use_container_width=True, hide_index=True)
    else:
        st.info("No intros data available.")


