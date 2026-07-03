import os
import uuid
import requests
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="PlacementIQ — by Pratik",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Background ── */
.stApp {
    background: #0f0f13;
    color: #e2e8f0;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2.5rem 3rem 2.5rem; max-width: 1400px; }

/* ── Hero banner ── */
.hero {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
    border-radius: 20px;
    padding: 2.8rem 3rem;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 260px; height: 260px;
    border-radius: 50%;
    background: rgba(255,255,255,0.07);
}
.hero::after {
    content: '';
    position: absolute;
    bottom: -40px; left: 40%;
    width: 180px; height: 180px;
    border-radius: 50%;
    background: rgba(255,255,255,0.05);
}
.hero-title {
    font-size: 2.6rem;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.5px;
    margin: 0;
}
.hero-sub {
    font-size: 1.05rem;
    color: rgba(255,255,255,0.78);
    margin-top: 0.5rem;
    font-weight: 400;
}
.hero-tag {
    display: inline-block;
    background: rgba(255,255,255,0.18);
    color: #fff;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 0.3rem 0.8rem;
    border-radius: 999px;
    margin-bottom: 1rem;
    backdrop-filter: blur(4px);
}

/* ── Stat cards ── */
.stat-card {
    background: #1a1a24;
    border: 1px solid #2d2d40;
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    transition: border-color 0.2s, transform 0.2s;
}
.stat-card:hover {
    border-color: #6366f1;
    transform: translateY(-2px);
}
.stat-num {
    font-size: 2.2rem;
    font-weight: 800;
    color: #a78bfa;
    line-height: 1;
}
.stat-label {
    font-size: 0.78rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-top: 0.35rem;
    font-weight: 500;
}

/* ── JD cards ── */
.jd-card {
    background: #1a1a24;
    border: 1px solid #2d2d40;
    border-radius: 14px;
    padding: 1.4rem;
    margin-bottom: 1rem;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.jd-card:hover {
    border-color: #6366f1;
    box-shadow: 0 0 24px rgba(99,102,241,0.12);
}
.jd-company {
    font-size: 1.1rem;
    font-weight: 700;
    color: #c4b5fd;
}
.jd-role {
    font-size: 0.92rem;
    color: #94a3b8;
    margin-top: 0.15rem;
    font-weight: 500;
}
.badge {
    display: inline-block;
    padding: 0.22rem 0.65rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    margin-right: 0.4rem;
    margin-top: 0.6rem;
}
.badge-ctc  { background: #1e3a5f; color: #60a5fa; }
.badge-cgpa { background: #3b2a00; color: #fbbf24; }
.badge-loc  { background: #1a3330; color: #34d399; }
.badge-type { background: #2d1a40; color: #c084fc; }

/* ── Chat ── */
.chat-user {
    background: #1e1e2e;
    border-left: 3px solid #6366f1;
    border-radius: 0 12px 12px 0;
    padding: 0.9rem 1.2rem;
    margin: 0.6rem 0;
    color: #e2e8f0;
}
.chat-ai {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-left: 3px solid #a855f7;
    border-radius: 0 12px 12px 0;
    padding: 0.9rem 1.2rem;
    margin: 0.6rem 0;
    color: #e2e8f0;
}
.source-chip {
    display: inline-block;
    background: #1e1e30;
    border: 1px solid #3d3d5c;
    border-radius: 8px;
    padding: 0.3rem 0.7rem;
    font-size: 0.75rem;
    color: #a78bfa;
    margin: 0.2rem 0.2rem 0 0;
    font-weight: 500;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #1a1a24;
    border-radius: 12px;
    padding: 0.3rem;
    gap: 0.2rem;
    border: 1px solid #2d2d40;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    color: #64748b !important;
    font-weight: 500;
    font-size: 0.87rem;
    padding: 0.5rem 1.2rem;
}
.stTabs [aria-selected="true"] {
    background: #6366f1 !important;
    color: #ffffff !important;
    font-weight: 600;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #13131a !important;
    border-right: 1px solid #2d2d40;
}
[data-testid="stSidebar"] * { color: #94a3b8 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #e2e8f0 !important; }

/* ── Inputs ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input {
    background: #1a1a24 !important;
    border: 1px solid #2d2d40 !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 2px rgba(99,102,241,0.2) !important;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.5rem 1.2rem !important;
    transition: opacity 0.2s, transform 0.15s !important;
}
.stButton > button:hover {
    opacity: 0.9 !important;
    transform: translateY(-1px) !important;
}

/* ── Divider ── */
hr { border-color: #2d2d40 !important; }

/* ── Metric ── */
[data-testid="metric-container"] {
    background: #1a1a24;
    border: 1px solid #2d2d40;
    border-radius: 12px;
    padding: 1rem;
}
[data-testid="metric-container"] label { color: #64748b !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #a78bfa !important;
    font-weight: 700 !important;
}

/* ── Pill suggestions ── */
.pill-row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.5rem 0 1rem 0; }
.pill {
    background: #1e1e30;
    border: 1px solid #3d3d5c;
    border-radius: 999px;
    padding: 0.3rem 0.9rem;
    font-size: 0.8rem;
    color: #a78bfa;
    font-weight: 500;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0f0f13; }
::-webkit-scrollbar-thumb { background: #2d2d40; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #6366f1; }
</style>
""", unsafe_allow_html=True)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "student_profile" not in st.session_state:
    st.session_state.student_profile = {
        "cgpa": 8.0, "branch": "CS",
        "skills": ["Python", "SQL"],
        "preferred_locations": ["Bangalore"],
        "preferred_job_type": "fte"
    }
if "chat_input_val" not in st.session_state:
    st.session_state.chat_input_val = None


def call_api(method: str, path: str, data: dict = None) -> dict:
    url = f"{API_BASE_URL}{path}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=10)
        elif method == "POST":
            r = requests.post(url, json=data, timeout=60)
        elif method == "PUT":
            r = requests.put(url, json=data, timeout=10)
        else:
            return {"error": "Invalid method"}
        if r.status_code == 200:
            return r.json()
        return {"error": f"API {r.status_code}: {r.text}"}
    except Exception as e:
        return {"error": f"Connection failed: {e}"}


health_data = call_api("GET", "/api/index/health")
system_healthy = "error" not in health_data

# ── SIDEBAR ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:1.2rem 0 0.5rem 0;'>
        <div style='font-size:1.6rem;font-weight:800;color:#c4b5fd;letter-spacing:-0.5px;'>
            🎯 PlacementIQ
        </div>
        <div style='font-size:0.78rem;color:#475569;margin-top:0.2rem;font-weight:500;'>
            Built by <span style='color:#a78bfa;font-weight:600;'>Pratik Suryavanshi</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown(f"""
    <div style='font-size:0.75rem;color:#475569;text-transform:uppercase;letter-spacing:1px;font-weight:600;margin-bottom:0.5rem;'>
        Session
    </div>
    <div style='font-family:monospace;font-size:0.8rem;color:#64748b;background:#1a1a24;
                padding:0.4rem 0.7rem;border-radius:8px;border:1px solid #2d2d40;'>
        {st.session_state.session_id[:16]}...
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if system_healthy:
        status_icon = "🟢" if health_data.get("status") == "healthy" else "🟡"
        ollama_icon = "✅" if health_data.get("ollama_status") == "up" else "❌"
        chroma_icon = "✅" if health_data.get("chroma_status") == "up" else "❌"
        sqlite_icon = "✅" if health_data.get("sqlite_status") == "up" else "❌"

        st.markdown(f"""
        <div style='font-size:0.75rem;color:#475569;text-transform:uppercase;letter-spacing:1px;font-weight:600;margin-bottom:0.7rem;'>
            System Status
        </div>
        <div style='background:#1a1a24;border:1px solid #2d2d40;border-radius:12px;padding:1rem;font-size:0.82rem;'>
            <div style='color:#e2e8f0;font-weight:600;margin-bottom:0.6rem;'>
                {status_icon} {health_data.get("status","").capitalize()}
            </div>
            <div style='color:#64748b;margin:0.25rem 0;'>{sqlite_icon} SQLite</div>
            <div style='color:#64748b;margin:0.25rem 0;'>{chroma_icon} ChromaDB</div>
            <div style='color:#64748b;margin:0.25rem 0;'>{ollama_icon} Ollama LLM</div>
            <div style='margin-top:0.8rem;color:#475569;font-size:0.75rem;'>
                📚 <span style='color:#a78bfa;font-weight:600;'>{health_data.get("indexed_document_count",0)}</span> JDs indexed
            </div>
            <div style='color:#475569;font-size:0.75rem;margin-top:0.2rem;'>
                🤖 {health_data.get("embedding_model","").split("/")[-1]}
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style='background:#2d1a1a;border:1px solid #7f1d1d;border-radius:12px;padding:1rem;
                    font-size:0.83rem;color:#f87171;'>
            🔴 Backend offline<br>
            <span style='color:#64748b;font-size:0.75rem;'>Start server on port 8000</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:0.72rem;color:#334155;text-align:center;padding-top:1rem;border-top:1px solid #1e1e2e;'>
        PlacementIQ · AI-Powered Campus Recruiting<br>
        <span style='color:#4c1d95;'>© Pratik Suryavanshi 2026</span>
    </div>
    """, unsafe_allow_html=True)


# ── HERO ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-tag">🎓 IIT Delhi · Campus Placement Intelligence</div>
    <div class="hero-title">PlacementIQ</div>
    <div class="hero-sub">
        Ask anything about JDs, compare offers, find your best match — powered by local AI.
        <br>Built &amp; maintained by <strong style="color:#fff;">Pratik Suryavanshi</strong>
    </div>
</div>
""", unsafe_allow_html=True)

# ── TABS ────────────────────────────────────────────────────────────────────
tab_chat, tab_browse, tab_compare, tab_analytics, tab_profile = st.tabs([
    "💬  Chat Agent",
    "📂  Browse JDs",
    "⚖️  Compare",
    "📊  Analytics",
    "👤  My Profile",
])


# ══════════════════════════════════════════════════════════════════════════
# 1 · CHAT TAB
# ══════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)

    # Render history
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="chat-user">
                <span style='font-size:0.72rem;color:#475569;font-weight:600;text-transform:uppercase;
                             letter-spacing:1px;'>You</span><br>{msg["content"]}
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-ai">
                <span style='font-size:0.72rem;color:#7c3aed;font-weight:600;text-transform:uppercase;
                             letter-spacing:1px;'>PlacementIQ</span><br>{msg["content"]}
            </div>""", unsafe_allow_html=True)

            if msg.get("sources"):
                chips = "".join(
                    f"<span class='source-chip'>📄 {s.get('company_name','?')} — {s.get('role_title','?')}</span>"
                    for s in msg["sources"]
                )
                st.markdown(f"<div style='margin-top:0.4rem;'>{chips}</div>", unsafe_allow_html=True)

            if msg.get("structured_data") and "matrix" in msg["structured_data"]:
                df = pd.DataFrame.from_dict(msg["structured_data"]["matrix"], orient="index")
                st.dataframe(df, use_container_width=True)

    # Quick-fire suggestion buttons
    st.markdown("<div style='margin-top:1rem;font-size:0.78rem;color:#475569;font-weight:600;"
                "text-transform:uppercase;letter-spacing:1px;'>Quick Questions</div>",
                unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    if c1.button("Which companies need Python?"):
        st.session_state.chat_input_val = "Which companies require Python skills?"
    if c2.button("Roles above ₹70k stipend"):
        st.session_state.chat_input_val = "Show roles with stipend above 70000 per month"
    if c3.button("Compare Samsung vs Nestle"):
        st.session_state.chat_input_val = "Compare Samsung Research and Nestle India JDs"

    user_query = st.chat_input("Ask about eligibility, packages, deadlines, skills…")

    if st.session_state.chat_input_val:
        user_query = st.session_state.chat_input_val
        st.session_state.chat_input_val = None

    if user_query:
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        st.markdown(f"""
        <div class="chat-user">
            <span style='font-size:0.72rem;color:#475569;font-weight:600;
                         text-transform:uppercase;letter-spacing:1px;'>You</span><br>{user_query}
        </div>""", unsafe_allow_html=True)

        with st.spinner("Thinking…"):
            api_res = call_api("POST", "/api/query",
                               {"query_text": user_query, "session_id": st.session_state.session_id})

        if "error" in api_res:
            st.error(api_res["error"])
        else:
            ans = api_res["response_text"]
            intent = api_res.get("agent_type", "search")
            gen_ms = api_res.get("generation_time_ms", 0)

            st.markdown(f"""
            <div class="chat-ai">
                <span style='font-size:0.72rem;color:#7c3aed;font-weight:600;
                             text-transform:uppercase;letter-spacing:1px;'>
                    PlacementIQ · {intent} · {gen_ms}ms
                </span><br>{ans}
            </div>""", unsafe_allow_html=True)

            sources = api_res.get("source_documents", [])
            if sources:
                chips = "".join(
                    f"<span class='source-chip'>📄 {s.get('company_name','?')} — {s.get('role_title','?')}</span>"
                    for s in sources
                )
                st.markdown(f"<div style='margin:0.4rem 0 0.6rem 0;'>{chips}</div>",
                            unsafe_allow_html=True)

            if api_res.get("structured_data") and "matrix" in api_res["structured_data"]:
                st.dataframe(
                    pd.DataFrame.from_dict(api_res["structured_data"]["matrix"], orient="index"),
                    use_container_width=True
                )

            suggestions = api_res.get("follow_up_suggestions", [])
            if suggestions:
                pills = "".join(f"<span class='pill'>💡 {s}</span>" for s in suggestions)
                st.markdown(f"<div class='pill-row'>{pills}</div>", unsafe_allow_html=True)

            st.session_state.chat_history.append({
                "role": "assistant",
                "content": ans,
                "sources": sources,
                "structured_data": api_res.get("structured_data")
            })

        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# 2 · BROWSE TAB
# ══════════════════════════════════════════════════════════════════════════
with tab_browse:
    docs_data = call_api("GET", "/api/documents")

    if "error" in docs_data:
        st.error("Could not load documents from backend.")
    elif not docs_data:
        st.info("No JDs indexed yet. Drop PDF/DOCX files into the `jd_files/` folder.")
    else:
        search_q = st.text_input("🔍  Search by company or role", placeholder="e.g. Samsung, Backend…")

        cols = st.columns(3)
        idx = 0
        for doc in docs_data:
            cname = doc.get("company_name", "Unknown")
            role  = doc.get("role_title", "Unknown")
            if search_q and search_q.lower() not in cname.lower() and search_q.lower() not in role.lower():
                continue

            pkg     = doc.get("package_ctc")
            cgpa    = doc.get("cgpa_cutoff")
            jtype   = (doc.get("job_type") or "N/A").upper()
            deadline = doc.get("deadline") or "N/A"

            badges = f"<span class='badge badge-type'>🏷 {jtype}</span>"
            if pkg:
                badges += f"<span class='badge badge-ctc'>💰 {pkg} LPA</span>"
            if cgpa:
                badges += f"<span class='badge badge-cgpa'>🎓 {cgpa} CGPA</span>"
            if deadline != "N/A":
                badges += f"<span class='badge badge-loc'>📅 {deadline}</span>"

            with cols[idx % 3]:
                st.markdown(f"""
                <div class="jd-card">
                    <div class="jd-company">{cname}</div>
                    <div class="jd-role">{role}</div>
                    <div style='margin-top:0.5rem;'>{badges}</div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("View details", key=f"det_{doc['doc_id']}"):
                    det = call_api("GET", f"/api/documents/{doc['doc_id']}")
                    if "error" not in det:
                        with st.expander(f"📋 {det['company_name']} — Full Details", expanded=True):
                            d1, d2 = st.columns(2)
                            d1.markdown(f"**Role:** {det.get('role_title')}")
                            d1.markdown(f"**Type:** {det.get('job_type','').upper()}")
                            d1.markdown(f"**CTC:** {det.get('package_ctc') or 'N/A'} LPA")
                            d1.markdown(f"**CGPA Cutoff:** {det.get('cgpa_cutoff') or 'N/A'}")
                            d2.markdown(f"**Work Mode:** {det.get('work_mode') or 'N/A'}")
                            d2.markdown(f"**Branches:** {', '.join(det.get('branches', [])) or 'N/A'}")
                            d2.markdown(f"**Skills:** {', '.join(det.get('skills', [])) or 'N/A'}")
                            d2.markdown(f"**Locations:** {', '.join(det.get('locations', [])) or 'N/A'}")
            idx += 1


# ══════════════════════════════════════════════════════════════════════════
# 3 · COMPARE TAB
# ══════════════════════════════════════════════════════════════════════════
with tab_compare:
    docs_data = call_api("GET", "/api/documents")

    if "error" in docs_data or len(docs_data) < 2:
        st.info("Need at least 2 indexed JDs to compare.")
    else:
        companies = list({doc["company_name"] for doc in docs_data})
        selected  = st.multiselect("Select 2 or more companies:", companies)

        if len(selected) >= 2:
            if st.button("⚖️  Generate Comparison"):
                query = "Compare " + " and ".join(selected)
                with st.spinner("Generating comparison matrix…"):
                    res = call_api("POST", "/api/query",
                                   {"query_text": query, "session_id": st.session_state.session_id})
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.markdown(f"""
                    <div class="chat-ai" style='margin-top:1rem;'>
                        <span style='font-size:0.72rem;color:#7c3aed;font-weight:600;
                                     text-transform:uppercase;letter-spacing:1px;'>Comparison Result</span>
                        <br>{res["response_text"]}
                    </div>""", unsafe_allow_html=True)

                    if res.get("structured_data") and "matrix" in res["structured_data"]:
                        st.markdown("#### Structured Matrix")
                        st.dataframe(
                            pd.DataFrame.from_dict(res["structured_data"]["matrix"], orient="index"),
                            use_container_width=True
                        )


# ══════════════════════════════════════════════════════════════════════════
# 4 · ANALYTICS TAB
# ══════════════════════════════════════════════════════════════════════════
with tab_analytics:
    analytics = call_api("GET", "/api/analytics/summary")

    if "error" in analytics:
        st.error("Could not load analytics.")
    else:
        # Top metrics row
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-num">{analytics.get('total_jobs', 0)}</div>
                <div class="stat-label">Total JDs Indexed</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-num">{analytics.get('average_package', 0):.1f} <span style='font-size:1rem;'>LPA</span></div>
                <div class="stat-label">Average Package</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-num">{analytics.get('max_package', 0):.1f} <span style='font-size:1rem;'>LPA</span></div>
                <div class="stat-label">Highest Package</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        ch1, ch2 = st.columns(2)

        with ch1:
            st.markdown("#### 🛠 Top Skills in Demand")
            skills_data = analytics.get("top_skills", {})
            if skills_data:
                df_skills = pd.DataFrame(
                    list(skills_data.items()), columns=["Skill", "Frequency"]
                ).sort_values("Frequency", ascending=False)
                st.bar_chart(df_skills.set_index("Skill"), color="#6366f1")
            else:
                st.info("No skill data yet.")

        with ch2:
            st.markdown("#### 📍 Jobs by Location")
            loc_data = analytics.get("location_distribution", {})
            if loc_data:
                df_loc = pd.DataFrame(
                    list(loc_data.items()), columns=["City", "Count"]
                )
                st.bar_chart(df_loc.set_index("City"), color="#a855f7")
            else:
                st.info("No location data yet.")


# ══════════════════════════════════════════════════════════════════════════
# 5 · PROFILE TAB
# ══════════════════════════════════════════════════════════════════════════
with tab_profile:
    st.markdown("""
    <div style='background:#1a1a24;border:1px solid #2d2d40;border-radius:14px;
                padding:1.4rem 1.6rem;margin-bottom:1.5rem;'>
        <div style='font-size:1rem;font-weight:700;color:#c4b5fd;margin-bottom:0.3rem;'>
            👤 Pratik Suryavanshi
        </div>
        <div style='font-size:0.82rem;color:#64748b;'>
            Set your eligibility profile. The Recommendation Agent uses this to filter matching JDs.
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        p_cgpa   = st.number_input("Your CGPA", min_value=0.0, max_value=10.0,
                                    value=st.session_state.student_profile["cgpa"], step=0.1)
        p_branch = st.selectbox("Branch", ["CS", "IT", "ECE", "EE", "ME", "CE"])
        p_jtype  = st.radio("Preferred Type", ["fte", "intern", "both"], horizontal=True)
    with c2:
        p_skills = st.text_area("Core Skills (comma-separated)",
                                 value=", ".join(st.session_state.student_profile["skills"]))
        p_locs   = st.text_area("Preferred Locations (comma-separated)",
                                 value=", ".join(st.session_state.student_profile["preferred_locations"]))

    if st.button("💾  Save Profile"):
        skills_list = [s.strip() for s in p_skills.split(",") if s.strip()]
        locs_list   = [l.strip() for l in p_locs.split(",") if l.strip()]
        st.session_state.student_profile = {
            "cgpa": p_cgpa, "branch": p_branch,
            "skills": skills_list,
            "preferred_locations": locs_list,
            "preferred_job_type": p_jtype
        }
        res = call_api("PUT", f"/api/profile/{st.session_state.session_id}", {
            "cgpa": p_cgpa, "branch": p_branch,
            "skills": skills_list,
            "preferred_locations": locs_list,
            "preferred_job_type": p_jtype
        })
        if "error" in res:
            st.error(res["error"])
        else:
            st.success("✅ Profile saved! Recommendations will now filter by your eligibility.")
