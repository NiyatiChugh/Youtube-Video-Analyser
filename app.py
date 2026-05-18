"""
app.py — Streamlit frontend for YT Analyzer AI
Run with: streamlit run app.py
"""

import streamlit as st
import httpx

API = "http://localhost:8000"

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="YT Analyzer AI",
    page_icon="▶️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Minimal custom CSS ────────────────────────────────────────────────────────

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

    .yt-card {
        background: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
    }

    .section-head {
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #89b4fa;
        margin-bottom: 0.4rem;
    }

    .pill {
        display: inline-block;
        background: #313244;
        border-radius: 20px;
        padding: 0.2rem 0.7rem;
        font-size: 0.82rem;
        margin: 0.2rem 0.2rem 0.2rem 0;
        color: #cdd6f4;
    }

    .note-card {
        background: #181825;
        border-left: 3px solid #89b4fa;
        border-radius: 6px;
        padding: 0.6rem 0.9rem;
        margin-bottom: 0.5rem;
    }
    .note-card h4 { color: #89b4fa; margin: 0 0 0.2rem 0; font-size: 0.9rem; }
    .note-card p  { color: #cdd6f4; margin: 0; font-size: 0.88rem; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar: key management ───────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ▶️ YT Analyzer AI")
    st.caption("Powered by Gemini")
    st.divider()

    st.markdown("### 🔑 API Key Manager")

    try:
        aliases = httpx.get(f"{API}/keys/list", timeout=5).json().get("aliases", [])
    except Exception:
        aliases = []
        st.warning("⚠️ API server not reachable.\nRun: `uvicorn api:app --reload`")

    with st.expander("➕ Save a new key", expanded=not aliases):
        alias_input = st.text_input("Alias (e.g. my-gemini)", key="alias_inp")
        key_input   = st.text_input("Gemini API Key", type="password", key="key_inp")
        if st.button("Save Key", use_container_width=True):
            if alias_input and key_input:
                r = httpx.post(
                    f"{API}/keys/save",
                    json={"alias": alias_input, "api_key": key_input},
                    timeout=5,
                )
                if r.status_code == 200:
                    st.success("Key saved! ✅")
                    st.rerun()
                else:
                    st.error(r.text)
            else:
                st.warning("Fill both fields.")

    if aliases:
        st.markdown("**Saved aliases:**")
        for a in aliases:
            st.markdown(f"- `{a}`")

    st.divider()
    st.caption("Keys are SHA-256 hashed before being stored on disk.")

# ── Main area ─────────────────────────────────────────────────────────────────

st.markdown("## Analyze a YouTube Video")

col_url, col_alias, col_btn = st.columns([5, 2, 1])
with col_url:
    yt_url = st.text_input(
        "YouTube URL",
        placeholder="https://www.youtube.com/watch?v=...",
        label_visibility="collapsed",
    )
with col_alias:
    chosen_alias = st.selectbox(
        "Key alias",
        options=aliases if aliases else ["(no keys saved)"],
        label_visibility="collapsed",
    )
with col_btn:
    run = st.button("▶ Analyze", use_container_width=True, type="primary")

st.divider()

# ── Trigger analysis ──────────────────────────────────────────────────────────

if run:
    if not yt_url:
        st.warning("Paste a YouTube URL first.")
    elif not aliases:
        st.error("No API key saved yet. Add one in the sidebar.")
    else:
        with st.spinner("Fetching transcript & asking Gemini… ~15 s"):
            try:
                resp = httpx.post(
                    f"{API}/analyze",
                    json={"alias": chosen_alias, "youtube_url": yt_url},
                    timeout=90,
                )
                if resp.status_code != 200:
                    st.error(f"Error {resp.status_code}: {resp.json().get('detail', resp.text)}")
                else:
                    st.session_state["result"] = resp.json()
            except httpx.ConnectError:
                st.error("Cannot connect to the API. Run `uvicorn api:app --reload` first.")

# ── Display results ───────────────────────────────────────────────────────────

if "result" in st.session_state:
    data     = st.session_state["result"]
    info     = data.get("videoInfo", {})
    video_id = data.get("videoId", "")

    left, right = st.columns([1, 2], gap="large")

    with left:
        if video_id:
            st.components.v1.iframe(
                f"https://www.youtube.com/embed/{video_id}",
                height=210,
                scrolling=False,
            )
        st.markdown(f"""
        <div class="yt-card">
            <div style="font-weight:600;color:#cdd6f4">{info.get('title', '')}</div>
            <div style="color:#a6adc8;font-size:0.85rem;margin-top:0.2rem">{info.get('channel', '')}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="section-head">📋 Summary</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="yt-card"><p style="color:#cdd6f4;margin:0">{data.get("summary", "")}</p></div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-head">✅ Action Items</div>', unsafe_allow_html=True)
        items_html = "".join(
            f'<div style="color:#a6e3a1;margin-bottom:0.3rem">• {i}</div>'
            for i in data.get("actionItems", [])
        )
        st.markdown(f'<div class="yt-card">{items_html}</div>', unsafe_allow_html=True)

    with right:
        tab1, tab2, tab3, tab4 = st.tabs(
            ["📖 Explanation", "📝 Detailed Notes", "💡 Study Topics", "⚡ Short Notes"]
        )

        with tab1:
            st.markdown(
                f'<div class="yt-card" style="line-height:1.7;color:#cdd6f4">'
                f'{data.get("properExplanation", "")}</div>',
                unsafe_allow_html=True,
            )

        with tab2:
            for note in data.get("detailedNotes", []):
                st.markdown(
                    f'<div class="note-card"><h4>{note["topic"]}</h4>'
                    f'<p>{note["content"]}</p></div>',
                    unsafe_allow_html=True,
                )

        with tab3:
            pills = "".join(
                f'<span class="pill">📌 {t}</span>'
                for t in data.get("studyTopics", [])
            )
            st.markdown(f'<div style="margin-top:0.5rem">{pills}</div>', unsafe_allow_html=True)

        with tab4:
            for n in data.get("shortNotes", []):
                st.markdown(
                    f'<div class="note-card" style="border-left-color:#f38ba8">'
                    f'<p>• {n}</p></div>',
                    unsafe_allow_html=True,
                )

    st.divider()
    if st.button("🗑 Clear results"):
        del st.session_state["result"]
        st.rerun()