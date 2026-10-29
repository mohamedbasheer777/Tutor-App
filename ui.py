"""
ui.py - Shared helpers used by every page:
styling, student sign-in (sidebar), cards, badges, charts, model loading.
"""

import html
import sys
from pathlib import Path

# Make sure the project folder is importable from the pages/ folder.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

import auth
import database
import recommender
from train_model import MODEL_PATH, load_model, train_and_save

APP_NAME = "Student Learning Companion"

# Colour tokens (also used by the CSS below)
INK, TEAL, VIOLET = "#14252b", "#0f766e", "#6d5bd0"
AMBER, CORAL, GREEN = "#f5b83d", "#d9482b", "#2f855a"
COLORWAY = [TEAL, VIOLET, AMBER, CORAL, "#64748b"]

CSS = """
<style>
:root {
  --ink: #14252b; --muted: #5b706d; --line: #dbe5e3;
  --teal: #0f766e; --amber: #f5b83d;
  --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --sans: "Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", sans-serif;
}
html, body, .stApp { font-family: var(--sans); }
.block-container { padding-top: 2rem; max-width: 1200px; }
.stApp h1, .stApp h2, .stApp h3 { font-family: var(--serif); color: var(--ink); letter-spacing: -.01em; }
.stApp h5 { color: var(--ink); }

/* ---------- header with notebook grid ---------- */
.hero {
  background-color: #0f2a2e;
  background-image:
    linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px);
  background-size: 24px 24px;
  border-radius: 16px; border-bottom: 4px solid var(--amber);
  padding: 1.6rem 1.8rem; margin-bottom: 1.4rem;
}
.hero-title { font-family: var(--serif); color: #fff; font-size: 2rem; font-weight: 700; line-height: 1.2; }
.hero-sub { color: #b9d3d0; margin-top: .35rem; font-size: 1.02rem; }

/* ---------- stat cards ---------- */
.card {
  background: #fff; color: var(--ink); border: 1px solid var(--line);
  border-left: 5px solid var(--accent, #0f766e); border-radius: 10px;
  padding: .85rem 1.1rem; margin-bottom: .6rem;
}
.card .label { font-size: .85rem; color: var(--muted); }
.card .value { font-family: var(--serif); font-size: 2rem; font-weight: 700; line-height: 1.25; }
.card .sub { font-size: .8rem; color: var(--muted); }

/* ---------- score ring ---------- */
.ring-panel {
  display: flex; align-items: center; gap: 1.2rem; background: #fff;
  border: 1px solid var(--line); border-radius: 14px; padding: 1.1rem 1.3rem; margin-bottom: .6rem;
}
.ring {
  --p: 0; --c: #0f766e; flex: none; width: 112px; height: 112px; border-radius: 50%;
  background: conic-gradient(var(--c) calc(var(--p) * 1%), #e3ebe9 0);
  display: grid; place-items: center;
}
.ring-inner {
  width: 84px; height: 84px; border-radius: 50%; background: #fff; display: grid;
  place-items: center; font-family: var(--serif); font-size: 1.55rem; font-weight: 700; color: var(--ink);
}
.ring-label { font-family: var(--serif); font-size: 1.15rem; font-weight: 700; color: var(--ink); }
.ring-sub { color: var(--muted); font-size: .9rem; margin-top: .2rem; }

/* ---------- highlighter panel: what to do next ---------- */
.nextup {
  background: #fff8e6; border: 1px solid #f1d58a; border-left: 5px solid var(--amber);
  border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: .6rem; color: var(--ink);
}
.nextup .t { font-family: var(--serif); font-size: 1.3rem; font-weight: 700; }
.nextup .m { color: #7a5b0c; font-size: .88rem; margin: .15rem 0 .4rem; }
.nextup .b { font-size: .95rem; }

/* ---------- empty state ---------- */
.empty {
  border: 2px dashed #b7c9c6; border-radius: 12px; padding: 1.2rem 1.4rem;
  text-align: center; color: var(--muted); background: rgba(255,255,255,.6); margin: .5rem 0 1rem;
}
.empty .t { font-family: var(--serif); font-size: 1.15rem; font-weight: 700; color: var(--ink); }

/* ---------- badges ---------- */
.badge { display: inline-block; padding: .12rem .65rem; border-radius: 999px; font-size: .78rem; font-weight: 600; }
.badge-high   { background: #fde4dc; color: #8f2a12; }
.badge-medium { background: #fdf0cc; color: #7a5300; }
.badge-low    { background: #dcf1e4; color: #1d5e3a; }
.badge-none   { background: #e6ecea; color: #4b5f5c; }
.badge-info   { background: #dff0ee; color: #0b5f58; }

/* ---------- Streamlit widgets ---------- */
[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
.stButton > button, [data-testid="stFormSubmitButton"] > button {
  border-radius: 8px; border: 1px solid #b7c9c6; font-weight: 600;
  transition: background .15s, border-color .15s, color .15s;
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
  border-color: var(--teal); color: var(--teal);
}
.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"],
[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] {
  background: var(--teal); border-color: var(--teal); color: #fff;
}
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
  background: #0b5f58; border-color: #0b5f58; color: #fff;
}
button:focus-visible, input:focus-visible { outline: 3px solid var(--amber) !important; outline-offset: 2px; }
[data-testid="stTabs"] button[role="tab"] { font-weight: 600; }
[data-testid="stExpander"] { border: 1px solid var(--line); border-radius: 10px; background: #fff; }
[data-testid="stChatMessage"] { background: #fff; border: 1px solid var(--line); border-radius: 12px; }
[data-testid="stMetric"] { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: .7rem 1rem; }

@media (max-width: 900px) {
  .hero-title { font-size: 1.5rem; }
  .ring-panel { flex-direction: column; text-align: center; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
"""

PRIORITY_BADGE = {
    "High": "badge-high", "Medium": "badge-medium",
    "Low": "badge-low", "Not started": "badge-none",
}


# ----------------------------------------------------------------------
# Small display helpers
# ----------------------------------------------------------------------
def hero(title, subtitle=""):
    st.markdown(
        f'<div class="hero"><div class="hero-title">{html.escape(str(title))}</div>'
        f'<div class="hero-sub">{html.escape(str(subtitle))}</div></div>',
        unsafe_allow_html=True,
    )


def card(label, value, sub="", color=TEAL):
    st.markdown(
        f'<div class="card" style="--accent:{color}">'
        f'<div class="label">{html.escape(str(label))}</div>'
        f'<div class="value">{html.escape(str(value))}</div>'
        f'<div class="sub">{html.escape(str(sub))}</div></div>',
        unsafe_allow_html=True,
    )


def ring(percent, label, sub=""):
    """A circular score indicator. Colour follows the score."""
    percent = max(0.0, min(100.0, float(percent)))
    color = GREEN if percent >= 70 else AMBER if percent >= 50 else CORAL
    st.markdown(
        f'<div class="ring-panel"><div class="ring" style="--p:{percent:.0f};--c:{color}">'
        f'<div class="ring-inner">{percent:.0f}%</div></div>'
        f'<div><div class="ring-label">{html.escape(str(label))}</div>'
        f'<div class="ring-sub">{html.escape(str(sub))}</div></div></div>',
        unsafe_allow_html=True,
    )


def next_up(title, meta, body):
    """The amber 'what to do next' panel."""
    st.markdown(
        f'<div class="nextup"><div class="t">{html.escape(str(title))}</div>'
        f'<div class="m">{html.escape(str(meta))}</div>'
        f'<div class="b">{html.escape(str(body))}</div></div>',
        unsafe_allow_html=True,
    )


def empty_state(title, text):
    st.markdown(
        f'<div class="empty"><div class="t">{html.escape(str(title))}</div>'
        f'<div>{html.escape(str(text))}</div></div>',
        unsafe_allow_html=True,
    )


def badge(text, css_class="badge-info"):
    return f'<span class="badge {css_class}">{html.escape(str(text))}</span>'


def priority_badge(level):
    return badge(level, PRIORITY_BADGE.get(level, "badge-none"))


def show_plot(fig):
    """Draw a Plotly chart in the app's style, at full width."""
    fig.update_layout(
        margin=dict(l=10, r=10, t=50, b=10),
        font=dict(family="Segoe UI, system-ui, sans-serif", color=INK),
        title_font=dict(family="Palatino Linotype, Georgia, serif", size=18),
        colorway=COLORWAY,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(gridcolor="#e3ebe9", zerolinecolor="#cfdbd9")
    fig.update_yaxes(gridcolor="#e3ebe9", zerolinecolor="#cfdbd9")
    try:
        st.plotly_chart(fig, width="stretch")
    except Exception:
        st.plotly_chart(fig, use_container_width=True)


def flash(kind, text):
    """Remember a message to show after the next page refresh."""
    st.session_state["_flash"] = (kind, text)


def show_flash():
    item = st.session_state.pop("_flash", None)
    if item:
        {"success": st.success, "error": st.error,
         "info": st.info, "warning": st.warning}[item[0]](item[1])

# ----------------------------------------------------------------------
# Model and recommendations
# ----------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _load_bundle(model_file_time):
    # model_file_time makes the cache refresh automatically after retraining
    return load_model()


def get_model():
    """Load the ML model. Trains it first if the file is missing. None if impossible."""
    try:
        if not MODEL_PATH.exists():
            with st.spinner("Training the model for the first time (a few seconds)..."):
                train_and_save()
        return _load_bundle(MODEL_PATH.stat().st_mtime)
    except Exception:
        try:
            with st.spinner("Re-training the model..."):
                train_and_save()
            return _load_bundle(MODEL_PATH.stat().st_mtime)
        except Exception:
            return None


def get_recs(student_id):
    return recommender.get_recommendations(student_id, get_model())


def sync_tasks(student_id):
    """Refresh study tasks from the latest results and return the recommendations."""
    recs = get_recs(student_id)
    recommender.sync_study_tasks(student_id, recs)
    return recs


# ----------------------------------------------------------------------
# Page setup and sidebar (called at the top of every page)
# ----------------------------------------------------------------------
def setup_page(title, icon, require_login=True):
    st.set_page_config(page_title=f"{title} | {APP_NAME}", page_icon=icon, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        database.init_db()
        auth.init_auth()
    except Exception as error:
        st.error(f"The database could not be opened: {error}")
        st.stop()
    student_id = _sidebar()
    show_flash()
    if student_id is None and require_login:
        hero("Please sign in", "Your learning data is private to your account")
        st.info("Open the Home page, then sign in or create an account.")
        if st.button("Go to Home page"):
            st.switch_page("app.py")
        st.stop()
    return student_id


def _sidebar():
    """Shows only the signed-in student. Never lists other students."""
    student_id = st.session_state.get("auth_student_id")
    student = database.get_student(student_id) if student_id else None
    with st.sidebar:
        st.markdown("### 🎓 Learning Companion")
        if student is None:
            st.session_state.pop("auth_student_id", None)
            st.caption("Not signed in.")
        else:
            st.write(f"Signed in as **{student['name']}**")
            if st.button("Sign out", key="sign_out"):
                st.session_state.clear()
                st.rerun()
            if get_model() is None:
                st.caption("⚠️ ML model unavailable. Rules-only mode.")
            else:
                st.caption("🤖 Random Forest ready (trained on synthetic data)")
        st.caption("Runs offline. No API keys.")
    return student["id"] if student else None

# ----------------------------------------------------------------------
# One topic: measured vs model vs rules (used by Quiz and Study Planner)
# ----------------------------------------------------------------------
def render_rec_details(rec):
    measured, ml = rec["measured"], rec["ml"]
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("##### 📏 Measured performance")
        st.caption("Actual results from your quiz history")
        if measured is None:
            st.write("Not practised yet.")
        else:
            previous = ("n/a (first attempt)" if measured["num_attempts"] < 2
                        else f"{measured['previous_score']:.0f}%")
            st.markdown(
                f"- Latest score: **{measured['latest_score']:.0f}%**\n"
                f"- Previous score: **{previous}**\n"
                f"- Average score: **{measured['average_score']:.0f}%**\n"
                f"- Best score: **{measured['best_score']:.0f}%**\n"
                f"- Attempts: **{measured['num_attempts']}**\n"
                f"- Days since last practice: **{measured['days_since_last_practice']}**"
            )

    with c2:
        st.markdown("##### 🤖 Model prediction")
        st.caption("Random Forest trained on synthetic data. A guide, not a measurement.")
        if ml is None:
            st.write("A prediction needs at least one quiz attempt." if measured is None
                     else "Model not available.")
        else:
            css = "badge-high" if ml["label"] == "Needs Practice" else "badge-low"
            st.markdown(
                f"{badge(ml['label'], css)} &nbsp; P(Needs Practice) = "
                f"**{ml['probability_needs_practice']:.2f}**",
                unsafe_allow_html=True,
            )
            for f in ml["factors"]:
                st.markdown(f"- **{f['feature']}** = {f['value']:g}: {f['meaning']} "
                            f"({f['effect']:+.2f})")

    with c3:
        st.markdown("##### 📐 Rule-based advice")
        st.caption("Fixed if-then rules, each worth some points")
        if measured is None:
            st.write("No rules apply until the first quiz.")
        else:
            if not rec["rules"]:
                st.write("No rules triggered.")
            for r in rec["rules"]:
                st.markdown(f"- **+{r['points']}** {r['rule']}: {r['explanation']}")
            st.markdown(
                f"Rule points **{rec['rule_points']}** + model part "
                f"(up to {recommender.ML_WEIGHT}) = priority score "
                f"**{rec['priority_score']}** ({rec['priority_level']})"
            )
    st.info(rec["advice"])