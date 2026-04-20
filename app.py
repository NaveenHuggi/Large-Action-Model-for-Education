import streamlit as st
import subprocess
import os
import json
import time
import glob
import csv
from summarizer import Summarizer
from config import DOMAIN_CONFIG

# ─────────────────────────────────────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LAM Research Engine",
    layout="wide",
    page_icon="🤖",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Premium CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  html, body, .stApp {
      background: #07091a;
      color: #e2e8f0;
      font-family: 'Inter', sans-serif;
  }

  /* ── Sidebar ── */
  .css-1d391kg, [data-testid="stSidebar"] {
      background: linear-gradient(180deg, #0d1226 0%, #0f1220 100%);
      border-right: 1px solid rgba(96,165,250,0.12);
  }

  /* ── Main area ── */
  .main .block-container {
      padding: 1.8rem 2rem 2rem 2rem;
      max-width: 100%;
  }

  /* ── Headings ── */
  h1 { color: #60a5fa !important; font-weight: 700; letter-spacing: -0.5px; }
  h2 { color: #93c5fd !important; font-weight: 600; }
  h3 { color: #bfdbfe !important; font-weight: 500; }

  /* ── Buttons ── */
  .stButton > button {
      border-radius: 10px;
      font-weight: 600;
      font-size: 0.9rem;
      transition: all 0.25s ease;
      width: 100%;
  }
  .stButton > button[kind="primary"] {
      background: linear-gradient(135deg, #1d4ed8, #4f46e5);
      border: none;
      color: white;
      padding: 0.55rem 1rem;
      box-shadow: 0 4px 14px rgba(79,70,229,0.3);
  }
  .stButton > button[kind="primary"]:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(79,70,229,0.5);
  }
  .stButton > button[kind="secondary"] {
      background: transparent;
      border: 1px solid #ef4444;
      color: #ef4444;
  }
  .stButton > button[kind="secondary"]:hover {
      background: rgba(239,68,68,0.1);
      transform: translateY(-1px);
  }

  /* ── Inputs ── */
  .stTextArea textarea, .stTextInput input {
      background: #0f1424 !important;
      border: 1px solid rgba(96,165,250,0.2) !important;
      border-radius: 8px !important;
      color: #e2e8f0 !important;
      font-family: 'Inter', sans-serif !important;
  }
  .stTextArea textarea:focus, .stTextInput input:focus {
      border-color: rgba(96,165,250,0.5) !important;
      box-shadow: 0 0 0 2px rgba(96,165,250,0.1) !important;
  }

  /* ── Domain Cards ── */
  .domain-card {
      background: linear-gradient(145deg, #0f1628 0%, #0c1020 100%);
      border: 1px solid rgba(255,255,255,0.07);
      border-radius: 16px;
      padding: 1.3rem 1.5rem;
      margin-bottom: 1.2rem;
      transition: box-shadow 0.3s ease, border-color 0.3s ease;
      position: relative;
      overflow: hidden;
  }
  .domain-card::before {
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 2px;
      background: linear-gradient(90deg, transparent, rgba(96,165,250,0.3), transparent);
  }
  .domain-card:hover {
      box-shadow: 0 6px 32px rgba(96,165,250,0.1);
      border-color: rgba(96,165,250,0.18);
  }
  .domain-title {
      font-size: 1.05rem;
      font-weight: 700;
      padding: 0.2rem 0 0.85rem 0;
      border-bottom: 1px solid rgba(255,255,255,0.07);
      margin-bottom: 1rem;
      display: flex;
      align-items: center;
      gap: 6px;
  }
  .yt-title   { color: #f87171; }
  .wiki-title { color: #34d399; }
  .sch-title  { color: #a78bfa; }
  .sum-title  { color: #60a5fa; }

  /* ── Result links inside cards ── */
  .result-link-row {
      display: flex;
      flex-direction: column;
      gap: 2px;
      padding: 0.5rem 0;
      border-bottom: 1px solid rgba(255,255,255,0.05);
  }
  .result-link-row:last-child { border-bottom: none; }
  .result-link-row a {
      color: #93c5fd;
      text-decoration: none;
      font-weight: 500;
      font-size: 0.9rem;
      transition: color 0.2s;
  }
  .result-link-row a:hover { color: #60a5fa; text-decoration: underline; }
  .result-url-text {
      color: #475569;
      font-size: 0.76rem;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 100%;
  }

  /* ── Log Terminal ── */
  .log-box {
      background: #040811;
      border: 1px solid rgba(96,165,250,0.12);
      border-radius: 10px;
      padding: 12px 14px;
      font-family: 'Courier New', monospace;
      font-size: 11.5px;
      height: 260px;
      overflow-y: auto;
      color: #4ade80;
      line-height: 1.6;
  }

  /* ── Metric Cards ── */
  .metric-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 6px;
  }
  .metric-chip {
      background: rgba(30,43,71,0.8);
      border: 1px solid rgba(96,165,250,0.1);
      border-radius: 8px;
      padding: 5px 11px;
      font-size: 0.76rem;
      color: #93c5fd;
      font-weight: 500;
  }
  .metric-chip span { color: #fff; font-weight: 700; }

  /* ── Status badges ── */
  .status-running  { color: #fbbf24; font-weight: 600; }
  .status-done     { color: #4ade80; font-weight: 600; }
  .status-idle     { color: #4b5563; font-weight: 600; }
  .status-waiting  { color: #64748b; font-weight: 400; font-style: italic; }

  /* ── Summary text ── */
  .summary-text {
      font-size: 0.88rem;
      line-height: 1.75;
      color: #cbd5e1;
      white-space: pre-wrap;
      max-height: 260px;
      overflow-y: auto;
      padding-right: 4px;
  }
  .summary-text::-webkit-scrollbar { width: 4px; }
  .summary-text::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 4px; }

  /* ── Progress stepper badges ── */
  .step-badge {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 20px;
      font-size: 0.72rem;
      font-weight: 600;
      margin-left: 6px;
  }
  .step-done    { background: rgba(20,83,45,0.7);  color: #4ade80; border: 1px solid rgba(74,222,128,0.2); }
  .step-running { background: rgba(146,64,14,0.7); color: #fbbf24; border: 1px solid rgba(251,191,36,0.2); }
  .step-pending { background: rgba(30,43,71,0.5);  color: #64748b; border: 1px solid rgba(100,116,139,0.2); }

  /* ── YouTube Embed Grid ── */
  .yt-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 4px;
  }
  .yt-thumb {
      display: flex;
      flex-direction: column;
      gap: 4px;
  }
  .yt-thumb iframe {
      width: 100%;
      height: 130px;
      border-radius: 6px;
      border: none;
  }
  .yt-label {
      font-size: 0.72rem;
      color: #64748b;
      line-height: 1.3;
      margin: 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
  }
</style>
""", unsafe_allow_html=True)




# ─────────────────────────────────────────────────────────────────────────────
# Session State Init
# ─────────────────────────────────────────────────────────────────────────────
for key, default in {
    "processes":      {},   # {domain: subprocess.Popen}
    "domain_order":   ["youtube", "wikipedia", "scholar"],
    "current_domain_idx": 0,
    "running":        False,
    "query":          "",
    "summary":        None,
    "run_complete":   False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
RESULTS_PATH    = "lam_dom_execution.log"
RESULTS_JSON    = "results.json"
METRICS_CSV     = "eval_metrics.csv"
DOMAIN_ORDER    = ["youtube", "wikipedia", "scholar"]

def load_results() -> dict:
    if os.path.exists(RESULTS_JSON):
        try:
            with open(RESULTS_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def load_log(tail=50) -> str:
    if os.path.exists("lam_dom_execution.log"):
        try:
            with open("lam_dom_execution.log", "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                return "".join(lines[-tail:])
        except Exception:
            pass
    return "Waiting for agent logs..."

def load_metrics() -> list[dict]:
    rows = []
    if os.path.exists(METRICS_CSV):
        try:
            with open(METRICS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception:
            pass
    return rows

def start_domain_process(domain: str, query: str):
    """Spawns agentic_loop.py for a single domain."""
    cfg  = DOMAIN_CONFIG[domain]
    task = cfg["task_template"].format(query=query)
    
    import urllib.parse
    url = cfg["start_url"]
    if "{query}" in url:
        url = url.format(query=urllib.parse.quote_plus(query))
        
    cmd  = [
        "python", "agentic_loop.py",
        "--task",   task,
        "--url",    url,
        "--domain", domain,
    ]
    cwd = os.path.dirname(os.path.abspath(__file__))
    return subprocess.Popen(cmd, cwd=cwd)

def render_result_items(items: list, color_class: str) -> str:
    pass # Deprecated in favor of native markdown rendering

def domain_step_badge(domain: str, idx: int, current_idx: int) -> str:
    if idx < current_idx:
        return '<span class="step-badge step-done">✓ Done</span>'
    elif idx == current_idx and st.session_state.running:
        return '<span class="step-badge step-running">⚡ Running</span>'
    else:
        return '<span class="step-badge step-pending">⏸ Pending</span>'


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — Prompt & Controls
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("##  LAM Research Engine")
    st.markdown("*Automated multi-domain research powered by local LLM inference.*")
    st.divider()

    st.markdown("###  Research Query")
    query_input = st.text_area(
        "Enter your research topic",
        value=st.session_state.query or "Artificial Intelligence in Healthcare",
        height=100,
        placeholder="e.g. Climate Change, Quantum Computing, CRISPR…",
        key="query_input_box",
    )

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        start_disabled = st.session_state.running
        if st.button(" Start", type="primary", disabled=start_disabled, key="btn_start"):
            # Clean up previous run artifacts
            for f in glob.glob("states/*.png"):
                try: os.remove(f)
                except: pass
            open("lam_dom_execution.log", "w").close()
            if os.path.exists(RESULTS_JSON):
                os.remove(RESULTS_JSON)

            st.session_state.query              = query_input.strip()
            st.session_state.running            = True
            st.session_state.current_domain_idx = 0
            st.session_state.processes          = {}
            st.session_state.summary            = None
            st.session_state.run_complete       = False

            # Kick off the FIRST domain immediately
            first_domain = DOMAIN_ORDER[0]
            proc = start_domain_process(first_domain, st.session_state.query)
            st.session_state.processes[first_domain] = proc
            st.rerun()

    with col2:
        stop_disabled = not st.session_state.running
        if st.button(" Stop", type="secondary", disabled=stop_disabled, key="btn_stop"):
            for proc in st.session_state.processes.values():
                try: proc.terminate()
                except: pass
            st.session_state.processes          = {}
            st.session_state.running            = False
            st.session_state.current_domain_idx = 0
            st.rerun()

    st.markdown("---")

    # ── Status Indicator ──────────────────────────────────────────────
    if st.session_state.running:
        idx = st.session_state.current_domain_idx
        if idx < len(DOMAIN_ORDER):
            current_label = DOMAIN_CONFIG[DOMAIN_ORDER[idx]]["label"]
            st.markdown(f'<p class="status-running"> Running: {current_label}</p>', unsafe_allow_html=True)
        else:
            st.markdown('<p class="status-done"> All domains complete!</p>', unsafe_allow_html=True)
    elif st.session_state.run_complete:
        st.markdown('<p class="status-done"> Research complete</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="status-idle"> Agent idle</p>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Metrics Panel ────────────────────────────────────────────────
    with st.expander(" Execution Metrics", expanded=False):
        metrics_rows = load_metrics()
        if not metrics_rows:
            st.caption("No metrics yet. Run the agent to capture data.")
        else:
            # Show the last 3 runs (most recent first)
            recent = metrics_rows[-3:][::-1]
            for row in recent:
                domain_lbl = DOMAIN_CONFIG.get(row.get("domain", ""), {}).get("label", row.get("domain", "—"))
                tsr  = float(row.get("tsr",  0))
                ssr  = float(row.get("ssr",  0))
                time_s = row.get("completion_time_sec", "—")
                skips  = row.get("steps_skipped", "0")
                st.markdown(f"""
                <div style="margin-bottom:10px;">
                  <div style="font-size:0.78rem;color:#64748b;">{row.get('timestamp','')}</div>
                  <div style="font-weight:600;font-size:0.85rem;color:#93c5fd;">{domain_lbl}</div>
                  <div class="metric-row">
                    <div class="metric-chip">TSR <span>{tsr:.0%}</span></div>
                    <div class="metric-chip">SSR <span>{ssr:.0%}</span></div>
                    <div class="metric-chip">Time <span>{time_s}s</span></div>
                    <div class="metric-chip">Skips <span>{skips}</span></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

    # ── Live Log ─────────────────────────────────────────────────────
    with st.expander("🖥️ Agent Log", expanded=True):
        log_ph = st.empty()
        log_text = load_log(tail=40)
        safe_log = log_text.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        log_ph.markdown(
            f'<div class="log-box">{safe_log}</div>',
            unsafe_allow_html=True
        )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN AREA — Results Panel
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("#  Research Results")

query_display = st.session_state.query or "—"
st.markdown(f"**Query:** `{query_display}`")
st.divider()

# Sequential orchestration: check if active domain process finished → start next
if st.session_state.running:
    idx = st.session_state.current_domain_idx

    if idx < len(DOMAIN_ORDER):
        current_domain = DOMAIN_ORDER[idx]
        proc = st.session_state.processes.get(current_domain)

        if proc is not None and proc.poll() is not None:
            # Current domain just finished → advance to next domain
            st.session_state.current_domain_idx += 1
            next_idx = st.session_state.current_domain_idx

            if next_idx < len(DOMAIN_ORDER):
                next_domain = DOMAIN_ORDER[next_idx]
                next_proc   = start_domain_process(next_domain, st.session_state.query)
                st.session_state.processes[next_domain] = next_proc
            else:
                # All domains done — generate summary
                st.session_state.running = False
                results_data = load_results()
                if results_data:
                    try:
                        summarizer = Summarizer()
                        st.session_state.summary = summarizer.generate_summary(
                            st.session_state.query, results_data
                        )
                    except Exception as e:
                        st.session_state.summary = f"Could not generate summary: {e}"
                st.session_state.run_complete = True
            st.rerun()

# Read current results from disk
results_data = load_results()

# ── Domain Cards — 2×2 Grid ───────────────────────────────────────────────────
DOMAIN_META = {
    "youtube":   {"icon": "", "color_cls": "yt-title",   "title": "YouTube"},
    "wikipedia": {"icon": "", "color_cls": "wiki-title",  "title": "Wikipedia"},
    "scholar":   {"icon": "", "color_cls": "sch-title",   "title": "Research Papers"},
}

import re as _re
import streamlit.components.v1 as _components

def extract_video_id(url: str) -> str | None:
    """Extracts the YouTube video ID from a watch URL."""
    match = _re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None

def render_youtube_component(items: list, badge_html: str):
    """
    Renders 4 YouTube embeds in a 2×2 grid using st.components.v1.html(),
    which creates a proper sandboxed iframe — the only reliable way to embed
    multiple YouTube players inside Streamlit.
    """
    grid_html = ""
    for item in (items or [])[:4]:
        vid_id = extract_video_id(item.get("url", ""))
        title  = (item.get("title", "Video")
                  .replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;"))
        if vid_id:
            grid_html += f"""
            <div class="yt-item">
              <iframe
                src="https://www.youtube.com/embed/{vid_id}"
                width="100%" height="148"
                frameborder="0"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowfullscreen>
              </iframe>
              <p class="yt-label" title="{title}">{title}</p>
            </div>"""

    waiting = not bool(grid_html)
    body = (grid_html if not waiting else
            '<p style="color:#64748b;font-style:italic;margin-top:12px;"> Collecting results…</p>')

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  *  {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
      background: linear-gradient(145deg, #0f1628 0%, #0c1020 100%);
      font-family: Inter, sans-serif;
      padding: 18px 18px 14px 18px;
      border: 1px solid rgba(255,255,255,0.07);
      border-radius: 16px;
      overflow: hidden;
  }}
  body::before {{
      content: '';
      display: block;
      height: 2px;
      margin: -18px -18px 16px -18px;
      background: linear-gradient(90deg, transparent, rgba(248,113,113,0.4), transparent);
      border-radius: 16px 16px 0 0;
  }}
  .header {{
      color: #f87171;
      font-size: 1rem;
      font-weight: 700;
      border-bottom: 1px solid rgba(255,255,255,0.07);
      padding-bottom: 10px;
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      gap: 8px;
  }}
  /* badge styles mirroring the main app */
  .step-badge   {{ border-radius: 20px; padding: 3px 10px; font-size: 0.71rem; font-weight: 600; }}
  .step-done    {{ background: rgba(20,83,45,0.7);   color: #4ade80; border: 1px solid rgba(74,222,128,0.2); }}
  .step-running {{ background: rgba(146,64,14,0.7);  color: #fbbf24; border: 1px solid rgba(251,191,36,0.2); }}
  .step-pending {{ background: rgba(30,43,71,0.5);   color: #64748b; border: 1px solid rgba(100,116,139,0.2); }}

  .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
  }}
  .yt-item {{
      display: flex;
      flex-direction: column;
      gap: 5px;
      min-width: 0;
  }}
  .yt-item iframe {{
      border-radius: 8px;
      display: block;
      background: #000;
  }}
  .yt-label {{
      font-size: 0.71rem;
      color: #64748b;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
  }}
</style>
</head>
<body>
  <div class="header"> YouTube {badge_html}</div>
  <div class="grid">{body}</div>
</body></html>"""

    _components.html(html, height=390, scrolling=False)


def build_links_card(domain: str, items: list, badge: str) -> str:
    """Renders Wikipedia / Scholar results as clean link rows inside a styled card."""
    meta = DOMAIN_META[domain]
    if not items:
        content = '<p class="status-waiting"> Collecting results…</p>'
    else:
        content = ""
        for item in items[:5]:
            title = item.get("title", "No title")
            url   = item.get("url", "#")
            content += f"""<div class="result-link-row">
  <a href="{url}" target="_blank">{title}</a>
  <span class="result-url-text">{url}</span>
</div>"""
    return f"""
    <div class="domain-card">
        <div class="domain-title {meta['color_cls']}">{meta['icon']} {meta['title']} {badge}</div>
        {content}
    </div>"""

# ── Row 1: YouTube (left) | Wikipedia (right) ─────────────────────────────────
col1, col2 = st.columns(2, gap="medium")

with col1:
    yt_items  = results_data.get("youtube", [])
    yt_badge  = domain_step_badge("youtube", 0, st.session_state.current_domain_idx)
    render_youtube_component(yt_items, yt_badge)

with col2:
    wiki_items = results_data.get("wikipedia", [])
    wiki_badge = domain_step_badge("wikipedia", 1, st.session_state.current_domain_idx)
    st.markdown(build_links_card("wikipedia", wiki_items, wiki_badge), unsafe_allow_html=True)

# ── Row 2: Research Papers (left) | Summary (right) ───────────────────────────
col3, col4 = st.columns(2, gap="medium")

with col3:
    sch_items = results_data.get("scholar", [])
    sch_badge = domain_step_badge("scholar", 2, st.session_state.current_domain_idx)
    st.markdown(build_links_card("scholar", sch_items, sch_badge), unsafe_allow_html=True)

with col4:
    if st.session_state.summary:
        summary_content = f'<div class="summary-text">{st.session_state.summary}</div>'
    elif st.session_state.running:
        summary_content = '<p class="status-waiting"> Summary will be generated after all domains complete…</p>'
    else:
        summary_content = '<p class="status-waiting">Run the agent to generate a research summary.</p>'

    st.markdown(f"""
    <div class="domain-card">
        <div class="domain-title sum-title"> Brief Summary</div>
        {summary_content}
    </div>
    """, unsafe_allow_html=True)

# ── Auto-refresh while running ────────────────────────────────────────────────
if st.session_state.running:
    time.sleep(1.5)
    st.rerun()
